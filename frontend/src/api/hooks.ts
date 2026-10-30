import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import type {
  AuthStatusOut,
  AuthTestOut,
  CopyHtmlOut,
  GenerateIn,
  Health,
  ImageOut,
  MemeFormatOut,
  JobOut,
  LinkedInPostOut,
  PersonaCreate,
  PersonaDuplicateIn,
  PersonaOut,
  PersonaUpdate,
  ProjectCreate,
  ProjectCreated,
  ProjectOut,
  ProjectSummary,
  ProjectUpdate,
  SampleOut,
  SampleWritingOut,
  SeedSamplesOut,
  SettingsIn,
  SettingsOut,
  UploadResult,
  VoiceProfileOut,
  VoiceProfileVersion,
} from './types.gen'

export const keys = {
  health: ['health'] as const,
  auth: ['auth'] as const,
  settings: ['settings'] as const,
  personas: ['personas'] as const,
  persona: (id: number) => ['personas', id] as const,
  samples: (personaId: number) => ['personas', personaId, 'samples'] as const,
  voiceProfile: (personaId: number, version?: number) => ['personas', personaId, 'voice-profile', version ?? 'latest'] as const,
  voiceProfileVersions: (personaId: number) => ['personas', personaId, 'voice-profile-versions'] as const,
  seed: ['seed-samples'] as const,
  sampleWriting: ['sample-writing'] as const,
  projects: ['projects'] as const,
  project: (id: number) => ['projects', id] as const,
  memeFormats: ['meme-formats'] as const,
}

// -- system --------------------------------------------------------------------

export const useHealth = () => useQuery({ queryKey: keys.health, queryFn: () => api.get<Health>('/api/health') })

export function useAuthStatus(poll = false) {
  return useQuery({
    queryKey: keys.auth,
    queryFn: () => api.get<AuthStatusOut>('/api/auth/status'),
    refetchInterval: (query) => (poll || query.state.data?.login_in_progress ? 2000 : false),
  })
}

export function useAuthActions() {
  const qc = useQueryClient()
  const update = (status: AuthStatusOut) => qc.setQueryData(keys.auth, status)
  return {
    login: useMutation({ mutationFn: () => api.post<AuthStatusOut>('/api/auth/login'), onSuccess: update }),
    claudeCodeLogin: useMutation({ mutationFn: () => api.post<AuthStatusOut>('/api/auth/claude-code/login'), onSuccess: update }),
    logout: useMutation({ mutationFn: () => api.post<AuthStatusOut>('/api/auth/logout'), onSuccess: update }),
    saveKey: useMutation({
      mutationFn: (apiKey: string) => api.put<AuthStatusOut>('/api/auth/api-key', { api_key: apiKey }),
      onSuccess: update,
    }),
    removeKey: useMutation({ mutationFn: () => api.del<AuthStatusOut>('/api/auth/api-key'), onSuccess: update }),
    test: useMutation({ mutationFn: () => api.post<AuthTestOut>('/api/auth/test') }),
  }
}

export const useSettings = () => useQuery({ queryKey: keys.settings, queryFn: () => api.get<SettingsOut>('/api/settings') })

export function useUpdateSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: SettingsIn) => api.put<SettingsOut>('/api/settings', body),
    onSuccess: (data, body) => {
      qc.setQueryData(keys.settings, data)
      // The sign-in status depends on which connection is chosen.
      if (body.claude_connection) void qc.invalidateQueries({ queryKey: keys.auth })
    },
  })
}

// -- personas ---------------------------------------------------------------------

export const usePersonas = () => useQuery({ queryKey: keys.personas, queryFn: () => api.get<PersonaOut[]>('/api/personas') })

export function useActivePersona() {
  const personas = usePersonas()
  return { ...personas, data: personas.data?.find((p) => p.is_active) }
}

export const usePersona = (id: number) =>
  useQuery({
    queryKey: keys.persona(id),
    queryFn: () => api.get<PersonaOut>(`/api/personas/${id}`),
    refetchInterval: (query) => (query.state.data?.active_job_id ? 3000 : false),
  })

export function usePersonaMutations() {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: keys.personas })
  return {
    create: useMutation({ mutationFn: (body: PersonaCreate) => api.post<PersonaOut>('/api/personas', body), onSuccess: refresh }),
    update: useMutation({
      mutationFn: ({ id, body }: { id: number; body: PersonaUpdate }) => api.patch<PersonaOut>(`/api/personas/${id}`, body),
      onSuccess: refresh,
    }),
    activate: useMutation({
      mutationFn: (id: number) => api.post<PersonaOut[]>(`/api/personas/${id}/activate`),
      onSuccess: (data) => {
        qc.setQueryData(keys.personas, data)
        void refresh()
      },
    }),
    remove: useMutation({
      mutationFn: (id: number) => api.del<void>(`/api/personas/${id}`),
      onSuccess: () => {
        void refresh()
        void qc.invalidateQueries({ queryKey: keys.projects })
      },
    }),
    /** Add the example persona, voice profile and finished post (built offline, no Claude call). */
    createExample: useMutation({
      mutationFn: () => api.post<PersonaOut>('/api/example'),
      // Wait for the refetch: callers navigate home next, and an empty cached list would send them back to the setup guide.
      onSuccess: () => Promise.all([refresh(), qc.invalidateQueries({ queryKey: keys.projects })]),
    }),
    removeExample: useMutation({
      mutationFn: () => api.del<void>('/api/example'),
      onSuccess: () => {
        void refresh()
        void qc.invalidateQueries({ queryKey: keys.projects })
      },
    }),
    duplicate: useMutation({
      mutationFn: ({ id, body }: { id: number; body: PersonaDuplicateIn }) => api.post<PersonaOut>(`/api/personas/${id}/duplicate`, body),
      onSuccess: refresh,
    }),
    generateVoiceProfile: useMutation({
      mutationFn: ({ id, label = '' }: { id: number; label?: string }) => api.post<JobOut>(`/api/personas/${id}/voice-profile`, { label }),
      onSuccess: refresh,
    }),
    /** Which voice profile version new posts use; null = always the latest. */
    pinVersion: useMutation({
      mutationFn: ({ id, version }: { id: number; version: number | null }) =>
        api.patch<PersonaOut>(`/api/personas/${id}`, { pinned_voice_profile_version: version }),
      onSuccess: (_data, { id }) => {
        void refresh()
        void qc.invalidateQueries({ queryKey: ['personas', id] })
      },
    }),
    /** Forget one learned edit (by index) or, without an index, all of them. */
    forgetLessons: useMutation({
      mutationFn: ({ id, index }: { id: number; index?: number }) =>
        api.del<PersonaOut>(`/api/personas/${id}/lessons${index === undefined ? '' : `?index=${index}`}`),
      onSuccess: (_data, { id }) => {
        void refresh()
        void qc.invalidateQueries({ queryKey: ['personas', id] })
      },
    }),
    labelVersion: useMutation({
      mutationFn: ({ id, version, label }: { id: number; version: number; label: string }) =>
        api.patch<VoiceProfileOut>(`/api/personas/${id}/voice-profile/${version}`, { label }),
      onSuccess: (_data, { id }) => {
        void refresh()
        void qc.invalidateQueries({ queryKey: ['personas', id] })
      },
    }),
  }
}

// -- samples & voice profile -------------------------------------------------------------

export const useSamples = (personaId: number) =>
  useQuery({ queryKey: keys.samples(personaId), queryFn: () => api.get<SampleOut[]>(`/api/personas/${personaId}/samples`) })

export const useSeedSamples = () => useQuery({ queryKey: keys.seed, queryFn: () => api.get<SeedSamplesOut>('/api/seed-samples') })

export const useSampleWriting = () => useQuery({ queryKey: keys.sampleWriting, queryFn: () => api.get<SampleWritingOut>('/api/sample-writing') })

export function useSampleMutations(personaId: number) {
  const qc = useQueryClient()
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: keys.samples(personaId) })
    void qc.invalidateQueries({ queryKey: keys.personas })
  }
  return {
    upload: useMutation({
      mutationFn: ({ files, kind }: { files: File[]; kind: 'own' | 'influence' }) => {
        const form = new FormData()
        files.forEach((file) => form.append('files', file))
        form.append('kind', kind)
        return api.post<UploadResult>(`/api/personas/${personaId}/samples`, form)
      },
      onSuccess: refresh,
    }),
    importUrl: useMutation({
      mutationFn: ({ url, kind }: { url: string; kind: 'own' | 'influence' }) => api.post<SampleOut>(`/api/personas/${personaId}/samples/url`, { url, kind }),
      onSuccess: refresh,
    }),
    importSampleWriting: useMutation({
      mutationFn: () => api.post<UploadResult>(`/api/personas/${personaId}/samples/import-sample-writing`),
      onSuccess: refresh,
    }),
    importSeed: useMutation({
      mutationFn: () => api.post<UploadResult>(`/api/personas/${personaId}/samples/import-seed`),
      onSuccess: refresh,
    }),
    setKind: useMutation({
      mutationFn: ({ id, kind }: { id: number; kind: 'own' | 'influence' }) => api.patch<SampleOut>(`/api/samples/${id}`, { kind }),
      onSuccess: refresh,
    }),
    remove: useMutation({ mutationFn: (id: number) => api.del<void>(`/api/samples/${id}`), onSuccess: refresh }),
  }
}

export const useVoiceProfile = (personaId: number, version?: number) =>
  useQuery({
    queryKey: keys.voiceProfile(personaId, version),
    queryFn: () => api.get<VoiceProfileOut>(`/api/personas/${personaId}/voice-profile${version ? `?version=${version}` : ''}`),
    retry: false,
  })

export const useVoiceProfileVersions = (personaId: number) =>
  useQuery({
    queryKey: keys.voiceProfileVersions(personaId),
    queryFn: () => api.get<VoiceProfileVersion[]>(`/api/personas/${personaId}/voice-profile/versions`),
  })

export function useSaveVoiceProfile(personaId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ markdown, label = '' }: { markdown: string; label?: string }) =>
      api.put<VoiceProfileOut>(`/api/personas/${personaId}/voice-profile`, { markdown, label }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['personas', personaId] })
      void qc.invalidateQueries({ queryKey: keys.personas })
    },
  })
}

// -- projects -----------------------------------------------------------------------------

export const useProjects = () => useQuery({ queryKey: keys.projects, queryFn: () => api.get<ProjectSummary[]>('/api/projects') })

export const useProject = (id: number) => useQuery({ queryKey: keys.project(id), queryFn: () => api.get<ProjectOut>(`/api/projects/${id}`) })

export function useProjectMutations(projectId?: number) {
  const qc = useQueryClient()
  const setProject = (data: ProjectOut) => {
    qc.setQueryData(keys.project(data.id), data)
    void qc.invalidateQueries({ queryKey: keys.projects })
  }
  return {
    create: useMutation({
      mutationFn: (body: ProjectCreate) => api.post<ProjectCreated>('/api/projects', body),
      onSuccess: (data) => setProject(data.project),
    }),
    update: useMutation({
      mutationFn: (body: ProjectUpdate) => api.patch<ProjectOut>(`/api/projects/${projectId}`, body),
      onSuccess: setProject,
    }),
    /** Write the whole post again; with a body, first apply a new brief, dials or persona. */
    generate: useMutation({
      mutationFn: (body?: GenerateIn) => api.post<JobOut>(`/api/projects/${projectId}/generate`, body),
      onSuccess: () => qc.invalidateQueries({ queryKey: keys.project(projectId ?? 0) }),
    }),
    /** Apply the author's feedback with surgical edits; text and images that are not mentioned stay. */
    tweak: useMutation({ mutationFn: (feedback: string) => api.post<JobOut>(`/api/projects/${projectId}/tweak`, { feedback }) }),
    /** Bring back an earlier text version (index 0 = undo the last change). */
    restoreRevision: useMutation({
      mutationFn: (index: number) => api.post<ProjectOut>(`/api/projects/${projectId}/revisions/${index}/restore`),
      onSuccess: setProject,
    }),
    rewrite: useMutation({
      mutationFn: (body: { selection: string; instruction: string }) => api.post<ProjectOut>(`/api/projects/${projectId}/rewrite`, body),
      onSuccess: setProject,
    }),
    /** Replace the title options; the current and pinned titles are kept. */
    regenerateTitles: useMutation({
      mutationFn: () => api.post<ProjectOut>(`/api/projects/${projectId}/titles`),
      onSuccess: setProject,
    }),
    /** Re-run the AI-generation detection report on the current text. */
    checkAuthenticity: useMutation({
      mutationFn: () => api.post<ProjectOut>(`/api/projects/${projectId}/authenticity`),
      onSuccess: setProject,
    }),
    remove: useMutation({
      mutationFn: (id: number) => api.del<void>(`/api/projects/${id}`),
      onSuccess: () => qc.invalidateQueries({ queryKey: keys.projects }),
    }),
  }
}

/** Every format a closing meme can take; it never changes while the app runs. */
export const useMemeFormats = (enabled = true) =>
  useQuery({ queryKey: keys.memeFormats, queryFn: () => api.get<MemeFormatOut[]>('/api/meme-formats'), staleTime: Infinity, enabled })

export function useImageMutations(projectId: number) {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: keys.project(projectId) })
  return {
    redraw: useMutation({
      mutationFn: ({ id, rethink, memeFormat }: { id: number; rethink: boolean; memeFormat?: string }) =>
        api.post<JobOut>(`/api/images/${id}/redraw`, { rethink, meme_format: memeFormat ?? null }),
    }),
    /** Redraw every image Claude drew, e.g. after changing the brand kit. */
    redrawAll: useMutation({ mutationFn: () => api.post<JobOut>(`/api/projects/${projectId}/images/redraw`) }),
    /** Change an image as described ("make the arrows orange"), keeping the rest of it. */
    edit: useMutation({
      mutationFn: ({ id, instruction }: { id: number; instruction: string }) => api.post<JobOut>(`/api/images/${id}/edit`, { instruction }),
    }),
    upload: useMutation({
      mutationFn: ({ id, file }: { id: number; file: File }) => {
        const form = new FormData()
        form.append('file', file)
        return api.post<ImageOut>(`/api/images/${id}/upload`, form)
      },
      onSuccess: refresh,
    }),
    revert: useMutation({
      mutationFn: ({ id, index }: { id: number; index: number }) => api.post<ImageOut>(`/api/images/${id}/revert`, { index }),
      onSuccess: refresh,
    }),
    update: useMutation({
      mutationFn: ({ id, ...body }: { id: number; caption?: string; alt?: string; credit?: string }) => api.patch<ImageOut>(`/api/images/${id}`, body),
      onSuccess: refresh,
    }),
  }
}

export const fetchCopyHtml = (projectId: number, platform: string) => api.get<CopyHtmlOut>(`/api/projects/${projectId}/copy/${platform}`)

export const useLinkedInPost = (projectId: number, enabled: boolean) =>
  useQuery({
    queryKey: [...keys.project(projectId), 'linkedin-post'],
    queryFn: () => api.get<LinkedInPostOut>(`/api/projects/${projectId}/linkedin-post`),
    enabled,
  })

export function useWriteLinkedInPost(projectId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<LinkedInPostOut>(`/api/projects/${projectId}/linkedin-post`),
    onSuccess: (data) => qc.setQueryData([...keys.project(projectId), 'linkedin-post'], data),
  })
}
