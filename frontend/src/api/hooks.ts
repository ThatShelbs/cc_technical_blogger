import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import type {
  AuthStatusOut,
  AuthTestOut,
  CopyHtmlOut,
  Dials,
  Health,
  ImageOut,
  JobOut,
  LinkedInPostOut,
  PersonaCreate,
  PersonaDuplicateIn,
  PersonaOut,
  PersonaUpdate,
  ProjectCreated,
  ProjectOut,
  ProjectSummary,
  ProjectUpdate,
  SampleOut,
  SeedSamplesOut,
  SettingsIn,
  SettingsOut,
  UploadResult,
  VoiceSoulOut,
  VoiceSoulVersion,
} from './types.gen'

export const keys = {
  health: ['health'] as const,
  auth: ['auth'] as const,
  settings: ['settings'] as const,
  personas: ['personas'] as const,
  persona: (id: number) => ['personas', id] as const,
  samples: (personaId: number) => ['personas', personaId, 'samples'] as const,
  voiceSoul: (personaId: number, version?: number) => ['personas', personaId, 'voice-soul', version ?? 'latest'] as const,
  voiceSoulVersions: (personaId: number) => ['personas', personaId, 'voice-soul-versions'] as const,
  seed: ['seed-samples'] as const,
  projects: ['projects'] as const,
  project: (id: number) => ['projects', id] as const,
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
    onSuccess: (data) => qc.setQueryData(keys.settings, data),
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
    duplicate: useMutation({
      mutationFn: ({ id, body }: { id: number; body: PersonaDuplicateIn }) => api.post<PersonaOut>(`/api/personas/${id}/duplicate`, body),
      onSuccess: refresh,
    }),
    generateVoiceSoul: useMutation({
      mutationFn: ({ id, label = '' }: { id: number; label?: string }) => api.post<JobOut>(`/api/personas/${id}/voice-soul`, { label }),
      onSuccess: refresh,
    }),
    /** Which voice soul version new posts use; null = always the latest. */
    pinVersion: useMutation({
      mutationFn: ({ id, version }: { id: number; version: number | null }) =>
        api.patch<PersonaOut>(`/api/personas/${id}`, { pinned_voice_soul_version: version }),
      onSuccess: (_data, { id }) => {
        void refresh()
        void qc.invalidateQueries({ queryKey: ['personas', id] })
      },
    }),
    labelVersion: useMutation({
      mutationFn: ({ id, version, label }: { id: number; version: number; label: string }) =>
        api.patch<VoiceSoulOut>(`/api/personas/${id}/voice-soul/${version}`, { label }),
      onSuccess: (_data, { id }) => {
        void refresh()
        void qc.invalidateQueries({ queryKey: ['personas', id] })
      },
    }),
  }
}

// -- samples & voice soul -------------------------------------------------------------

export const useSamples = (personaId: number) =>
  useQuery({ queryKey: keys.samples(personaId), queryFn: () => api.get<SampleOut[]>(`/api/personas/${personaId}/samples`) })

export const useSeedSamples = () => useQuery({ queryKey: keys.seed, queryFn: () => api.get<SeedSamplesOut>('/api/seed-samples') })

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

export const useVoiceSoul = (personaId: number, version?: number) =>
  useQuery({
    queryKey: keys.voiceSoul(personaId, version),
    queryFn: () => api.get<VoiceSoulOut>(`/api/personas/${personaId}/voice-soul${version ? `?version=${version}` : ''}`),
    retry: false,
  })

export const useVoiceSoulVersions = (personaId: number) =>
  useQuery({
    queryKey: keys.voiceSoulVersions(personaId),
    queryFn: () => api.get<VoiceSoulVersion[]>(`/api/personas/${personaId}/voice-soul/versions`),
  })

export function useSaveVoiceSoul(personaId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ markdown, label = '' }: { markdown: string; label?: string }) =>
      api.put<VoiceSoulOut>(`/api/personas/${personaId}/voice-soul`, { markdown, label }),
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
      mutationFn: (body: { prompt: string; dials?: Dials; persona_id?: number | null; generate?: boolean }) => api.post<ProjectCreated>('/api/projects', body),
      onSuccess: (data) => setProject(data.project),
    }),
    update: useMutation({
      mutationFn: (body: ProjectUpdate) => api.patch<ProjectOut>(`/api/projects/${projectId}`, body),
      onSuccess: setProject,
    }),
    generate: useMutation({ mutationFn: () => api.post<JobOut>(`/api/projects/${projectId}/generate`) }),
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

export function useImageMutations(projectId: number) {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: keys.project(projectId) })
  return {
    redraw: useMutation({
      mutationFn: ({ id, rethink }: { id: number; rethink: boolean }) => api.post<JobOut>(`/api/images/${id}/redraw`, { rethink }),
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
