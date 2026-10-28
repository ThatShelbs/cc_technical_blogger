import { ChevronDown, ListTree, RefreshCw, RotateCcw, Undo2 } from 'lucide-react'
import { useState } from 'react'

import { errorText } from '../../api/client'
import { usePersonas, useProjectMutations } from '../../api/hooks'
import type { JobOut, ProjectOut } from '../../api/types.gen'
import { DialsFields } from '../../components/DialsFields'
import { Button, Dialog, Field, Notice, Select, Textarea } from '../../components/ui'
import { planOutline } from '../../lib/outline'
import { PLATFORMS, buildDials, dialsToState, emptyDials, type DialsState, type Platform } from '../dials'

/** Edit the brief, persona and settings that wrote this post, then regenerate it. Nothing is saved until then. */
export function PostSettingsDialog({
  project,
  open,
  onClose,
  onStarted,
}: {
  project: ProjectOut
  open: boolean
  onClose: () => void
  onStarted: (job: JobOut) => void
}) {
  return (
    <Dialog open={open} onClose={onClose} title="Brief & settings" wide>
      {/* Mounted only while open, so every opening starts from the post's saved brief and settings. */}
      {open && <SettingsForm project={project} onStarted={onStarted} />}
    </Dialog>
  )
}

function SettingsForm({ project, onStarted }: { project: ProjectOut; onStarted: (job: JobOut) => void }) {
  const { generate } = useProjectMutations(project.id)
  const { data: personas = [] } = usePersonas()
  const [prompt, setPrompt] = useState(project.prompt)
  const [personaId, setPersonaId] = useState(project.persona_id)
  const [dials, setDials] = useState<DialsState>(() => dialsToState(project.dials))
  const [showPlan, setShowPlan] = useState(false)
  const set = (patch: Partial<DialsState>) => setDials((d) => ({ ...d, ...patch }))

  const persona = personas.find((p) => p.id === personaId)
  const writable = personas.filter((p) => p.voice_profile_version || p.id === project.persona_id)
  const platform = dials.platform ?? (persona?.default_platform as Platform | undefined) ?? 'medium'
  const outline = planOutline(project.plan)
  const changedDials = Object.keys(buildDials(dials)).length > 0
  const canWrite = prompt.trim().length >= 3 && !!persona?.voice_profile_version

  const submit = () => {
    // revision_passes is not on the form; keep it if the post had one.
    const passes = project.dials?.revision_passes
    generate.mutate(
      { prompt: prompt.trim(), persona_id: personaId, dials: { ...buildDials(dials), ...(passes !== undefined ? { revision_passes: Number(passes) } : {}) } },
      { onSuccess: onStarted },
    )
  }

  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
    >
      <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_16rem]">
        <div className="min-w-0 space-y-4">
          <Field label="Brief or outline" hint="What this post was written from. Refine it, add bullets, or paste a new outline." htmlFor="settings-prompt">
            <Textarea id="settings-prompt" rows={12} value={prompt} onChange={(e) => setPrompt(e.target.value)} required minLength={3} />
          </Field>
          {prompt !== project.prompt && (
            <Button type="button" size="sm" variant="ghost" icon={<Undo2 className="size-4" />} onClick={() => setPrompt(project.prompt)}>
              Revert to original brief
            </Button>
          )}
          {outline && (
            <div className="rounded-lg border border-line">
              <button
                type="button"
                className="flex w-full items-center justify-between px-3 py-2 text-sm font-semibold"
                aria-expanded={showPlan}
                onClick={() => setShowPlan((v) => !v)}
              >
                Outline Claude planned
                <ChevronDown className={`size-4 transition ${showPlan ? 'rotate-180' : ''}`} aria-hidden />
              </button>
              {showPlan && (
                <div className="space-y-2 border-t border-line p-3">
                  <pre className="max-h-56 overflow-auto text-xs whitespace-pre-wrap text-muted">{outline}</pre>
                  <Button type="button" size="sm" variant="secondary" icon={<ListTree className="size-4" />} onClick={() => setPrompt(outline)}>
                    Use as my outline
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="space-y-5">
          <Field label="Persona" htmlFor="settings-persona">
            <Select id="settings-persona" value={personaId} onChange={(e) => setPersonaId(Number(e.target.value))}>
              {writable.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                  {p.voice_profile_version ? '' : ' (no voice profile)'}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Publishing on" htmlFor="settings-platform">
            <Select id="settings-platform" value={platform} onChange={(e) => set({ platform: e.target.value as Platform })}>
              {PLATFORMS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
          <DialsFields dials={dials} onChange={set} persona={persona} idPrefix="settings-" />
          <Button type="button" variant="ghost" size="sm" icon={<RotateCcw className="size-4" />} disabled={!changedDials} onClick={() => setDials(emptyDials)}>
            Reset to persona defaults
          </Button>
        </div>
      </div>

      {persona && !persona.voice_profile_version && (
        <Notice tone="warn">{persona.name} has no voice profile yet. Pick another persona or generate one first.</Notice>
      )}
      {generate.error && <Notice tone="error">{errorText(generate.error)}</Notice>}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
        <p className="text-sm text-muted">Regenerating replaces the current text and images. Pinned titles are kept.</p>
        <Button type="submit" variant="flame" icon={<RefreshCw className="size-4" />} disabled={!canWrite} loading={generate.isPending}>
          Regenerate with these settings
        </Button>
      </div>
    </form>
  )
}
