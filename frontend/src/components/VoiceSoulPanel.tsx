import { useQueryClient } from '@tanstack/react-query'
import { Check, Flame, History, Pencil, PencilLine, Pin, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'

import { ApiError, errorText } from '../api/client'
import { keys, usePersona, usePersonaMutations, useSaveVoiceSoul, useVoiceSoul } from '../api/hooks'
import type { PersonaOut } from '../api/types.gen'
import { useJob } from '../api/useJob'
import { Markdown } from './Article'
import { Badge, Button, Card, Dialog, EmptyState, Field, Input, Notice, ProgressBar, Select, Textarea } from './ui'
import { cx } from '../lib/cx'

const STAT_LABELS: [string, string, (v: number) => string][] = [
  ['avg_sentence_words', 'Words per sentence', (v) => v.toFixed(1)],
  ['avg_paragraph_words', 'Words per paragraph', (v) => v.toFixed(0)],
  ['short_paragraph_ratio', 'One-sentence paragraphs', (v) => `${Math.round(v * 100)}%`],
  ['flesch_reading_ease', 'Reading ease', (v) => v.toFixed(0)],
  ['words_per_heading', 'Words per heading', (v) => v.toFixed(0)],
  ['words_per_image', 'Words per image', (v) => v.toFixed(0)],
]

/** Generate a new voice soul: as a named version of this persona, or as a brand-new persona. */
function GenerateDialog({
  persona,
  open,
  onClose,
  onStarted,
}: {
  persona: PersonaOut
  open: boolean
  onClose: () => void
  onStarted: (jobId: string) => void
}) {
  const mutations = usePersonaMutations()
  const navigate = useNavigate()
  const [target, setTarget] = useState<'version' | 'persona'>('version')
  const [label, setLabel] = useState('')
  const [name, setName] = useState('')
  const pending = mutations.generateVoiceSoul.isPending || mutations.duplicate.isPending
  const error = mutations.generateVoiceSoul.error ?? mutations.duplicate.error

  const submit = () => {
    if (target === 'version') {
      mutations.generateVoiceSoul.mutate(
        { id: persona.id, label },
        {
          onSuccess: (job) => {
            onStarted(job.id)
            onClose()
          },
        },
      )
      return
    }
    mutations.duplicate.mutate(
      { id: persona.id, body: { name: name.trim(), voice_soul_version: null, copy_samples: true } },
      {
        onSuccess: (created) =>
          mutations.generateVoiceSoul.mutate(
            { id: created.id, label },
            {
              onSuccess: () => {
                onClose()
                navigate(`/personas/${created.id}`)
              },
            },
          ),
      },
    )
  }

  return (
    <Dialog open={open} onClose={onClose} title="Generate a voice soul">
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        <div className="grid gap-2" role="radiogroup" aria-label="Save the new voice soul as">
          {(
            [
              ['version', `A new version of ${persona.name}`, 'Older versions stay in the history; you can switch back any time.'],
              ['persona', 'A new, separately named persona', 'Copies the samples and settings, then generates its own voice soul.'],
            ] as const
          ).map(([value, title, hint]) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={target === value}
              onClick={() => setTarget(value)}
              className={cx('rounded-xl border px-4 py-3 text-left', target === value ? 'border-accent bg-accent-soft' : 'border-line hover:bg-surface-2')}
            >
              <span className="block font-semibold">{title}</span>
              <span className="block text-sm text-muted">{hint}</span>
            </button>
          ))}
        </div>
        {target === 'persona' && (
          <Field label="New persona name" htmlFor="gen-name">
            <Input id="gen-name" value={name} onChange={(e) => setName(e.target.value)} placeholder={`${persona.name} (LinkedIn)`} required maxLength={80} />
          </Field>
        )}
        <Field label="Version name (optional)" hint="Helps you tell versions apart, e.g. “After adding 2025 posts”." htmlFor="gen-label">
          <Input id="gen-label" value={label} onChange={(e) => setLabel(e.target.value)} maxLength={80} />
        </Field>
        {error && <Notice tone="error">{errorText(error)}</Notice>}
        <Button type="submit" variant="flame" icon={<Flame className="size-4" />} loading={pending} disabled={target === 'persona' && !name.trim()}>
          Generate
        </Button>
      </form>
    </Dialog>
  )
}

function VersionLabel({ personaId, version, label }: { personaId: number; version: number; label: string }) {
  const { labelVersion } = usePersonaMutations()
  const [value, setValue] = useState<string | null>(null)
  if (value === null) {
    return (
      <button type="button" className="inline-flex items-center gap-1 text-sm text-muted hover:text-fg" onClick={() => setValue(label)}>
        {label ? <span className="font-semibold text-fg">{label}</span> : 'Name this version'}
        <Pencil className="size-3.5" aria-hidden />
      </button>
    )
  }
  return (
    <form
      className="flex items-center gap-1"
      onSubmit={(e) => {
        e.preventDefault()
        labelVersion.mutate({ id: personaId, version, label: value }, { onSuccess: () => setValue(null) })
      }}
    >
      <Input
        aria-label="Version name"
        className="h-8 w-56 text-sm"
        value={value}
        maxLength={80}
        autoFocus
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === 'Escape' && setValue(null)}
      />
      <Button type="submit" size="sm" icon={<Check className="size-4" />} loading={labelVersion.isPending} aria-label="Save version name" />
    </form>
  )
}

export function VoiceSoulPanel({ personaId, onGenerated }: { personaId: number; onGenerated?: () => void }) {
  const qc = useQueryClient()
  const persona = usePersona(personaId)
  const [version, setVersion] = useState<number | undefined>()
  const soul = useVoiceSoul(personaId, version)
  const mutations = usePersonaMutations()
  const save = useSaveVoiceSoul(personaId)
  const [jobId, setJobId] = useState<string | null>(null)
  const [editing, setEditing] = useState<{ markdown: string; label: string } | null>(null)
  const [generateOpen, setGenerateOpen] = useState(false)
  const runningJobId = jobId ?? persona.data?.active_job_id ?? null

  const job = useJob(runningJobId, (state) => {
    setJobId(null)
    void qc.invalidateQueries({ queryKey: ['personas'] })
    void qc.invalidateQueries({ queryKey: keys.voiceSoulVersions(personaId) })
    setVersion(undefined)
    if (state.status === 'succeeded') onGenerated?.()
  })

  const ownSamples = persona.data?.own_samples ?? 0
  const versions = persona.data?.voice_soul_versions ?? []
  const missing = soul.error instanceof ApiError && soul.error.status === 404
  const running = !!runningJobId && job.status !== 'succeeded' && job.status !== 'failed'
  const pinned = persona.data?.pinned_voice_soul_version ?? null

  const pin = (value: number | null) =>
    mutations.pinVersion.mutate(
      { id: personaId, version: value },
      {
        onSuccess: () => {
          setVersion(undefined)
          void qc.invalidateQueries({ queryKey: ['personas', personaId, 'voice-soul'] })
        },
      },
    )

  if (running) {
    return (
      <Card className="space-y-4" aria-live="polite">
        <div className="flex items-center gap-3">
          <Flame className="size-6 text-accent" aria-hidden />
          <div>
            <h2 className="text-lg font-bold">Synthesizing your voice soul</h2>
            <p className="text-sm text-muted">{job.message || 'Starting…'}</p>
          </div>
        </div>
        <ProgressBar value={job.progress} label="Voice soul progress" />
        {job.voice && (
          <div className="article max-h-[28rem] overflow-auto rounded-xl border border-line bg-sunken p-5 text-base">
            <Markdown>{job.voice}</Markdown>
          </div>
        )}
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {job.status === 'failed' && (
        <Notice tone="error" title="Voice soul generation failed">
          {job.error}
        </Notice>
      )}
      {mutations.generateVoiceSoul.error && <Notice tone="error">{errorText(mutations.generateVoiceSoul.error)}</Notice>}
      {ownSamples > 0 && ownSamples < 3 && <Notice tone="warn">Voice quality improves a lot with 3 or more of your own posts. You have {ownSamples}.</Notice>}

      {missing || !soul.data ? (
        <EmptyState
          icon={<Flame className="size-8" />}
          title="No voice soul yet"
          action={
            <Button
              variant="flame"
              size="lg"
              onClick={() => mutations.generateVoiceSoul.mutate({ id: personaId }, { onSuccess: (created) => setJobId(created.id) })}
              disabled={ownSamples === 0}
              loading={mutations.generateVoiceSoul.isPending}
            >
              Generate my voice soul
            </Button>
          }
        >
          {ownSamples === 0
            ? 'Add at least one post you wrote, then generate.'
            : 'Proseferno studies your posts (and any influences), then writes a field guide to your voice that every post follows.'}
        </EmptyState>
      ) : editing !== null ? (
        <Card className="space-y-3">
          <h2 className="font-bold">Edit voice soul</h2>
          <p className="text-sm text-muted">Saving creates a new version and starts using it; older versions stay in the history.</p>
          <Field label="Version name (optional)" htmlFor="edit-label">
            <Input id="edit-label" value={editing.label} maxLength={80} onChange={(e) => setEditing({ ...editing, label: e.target.value })} />
          </Field>
          <Textarea
            value={editing.markdown}
            onChange={(e) => setEditing({ ...editing, markdown: e.target.value })}
            rows={24}
            className="font-mono text-sm"
            aria-label="Voice soul markdown"
          />
          <div className="flex gap-2">
            <Button
              loading={save.isPending}
              onClick={() =>
                save.mutate(editing, {
                  onSuccess: () => {
                    setEditing(null)
                    setVersion(undefined)
                    void qc.invalidateQueries({ queryKey: keys.voiceSoulVersions(personaId) })
                  },
                })
              }
            >
              Save as new version
            </Button>
            <Button variant="ghost" onClick={() => setEditing(null)}>
              Cancel
            </Button>
          </div>
        </Card>
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="accent">Version {soul.data.version}</Badge>
              {soul.data.in_use ? <Badge tone="success">{pinned ? 'In use (pinned)' : 'In use'}</Badge> : <Badge>Not in use</Badge>}
              {soul.data.edited_by_user && <Badge>Edited by you</Badge>}
              <Badge>
                {soul.data.sample_count} sample{soul.data.sample_count === 1 ? '' : 's'}
              </Badge>
              {soul.data.best_practices && <Badge>Includes web research</Badge>}
              <VersionLabel key={`${soul.data.version}-${soul.data.label}`} personaId={personaId} version={soul.data.version} label={soul.data.label} />
            </div>
            <div className="flex flex-wrap gap-2">
              {versions.length > 1 && (
                <label className="flex items-center gap-2 text-sm">
                  <History className="size-4 text-muted" aria-hidden />
                  <span className="sr-only">Version</span>
                  <Select className="h-9 w-64" value={version ?? ''} onChange={(e) => setVersion(e.target.value ? Number(e.target.value) : undefined)}>
                    <option value="">In use (v{persona.data?.voice_soul_version})</option>
                    {versions.map((v) => (
                      <option key={v.id} value={v.version}>
                        v{v.version}
                        {v.label ? ` · ${v.label}` : ''} · {new Date(v.created_at).toLocaleDateString()}
                        {v.edited_by_user ? ' (edited)' : ''}
                      </option>
                    ))}
                  </Select>
                </label>
              )}
              {!soul.data.in_use && (
                <Button
                  size="sm"
                  variant="secondary"
                  icon={<Pin className="size-4" />}
                  loading={mutations.pinVersion.isPending}
                  onClick={() => pin(soul.data.version)}
                >
                  Use this version
                </Button>
              )}
              {pinned !== null && soul.data.in_use && (
                <Button size="sm" variant="ghost" loading={mutations.pinVersion.isPending} onClick={() => pin(null)}>
                  Always use latest
                </Button>
              )}
              <Button
                variant="secondary"
                size="sm"
                icon={<PencilLine className="size-4" />}
                onClick={() => setEditing({ markdown: soul.data.markdown, label: '' })}
              >
                Edit
              </Button>
              <Button size="sm" icon={<RefreshCw className="size-4" />} onClick={() => setGenerateOpen(true)}>
                Regenerate
              </Button>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {STAT_LABELS.map(([key, label, fmt]) => {
              const value = soul.data.baseline_stylometrics[key]
              return typeof value === 'number' ? (
                <div key={key} className="rounded-xl border border-line bg-surface p-3">
                  <p className="text-xs text-muted">{label}</p>
                  <p className="text-lg font-bold tabular-nums">{fmt(value)}</p>
                </div>
              ) : null
            })}
          </div>

          <Card padded={false} className="article max-w-none p-6 text-base sm:p-8">
            <Markdown>{soul.data.markdown}</Markdown>
          </Card>
          {soul.data.best_practices && (
            <details className="rounded-2xl border border-line bg-surface p-5">
              <summary className="cursor-pointer font-semibold">Web research on best practices</summary>
              <div className="article mt-4 text-base">
                <Markdown>{soul.data.best_practices}</Markdown>
              </div>
            </details>
          )}
        </>
      )}
      {persona.data && generateOpen && <GenerateDialog persona={persona.data} open onClose={() => setGenerateOpen(false)} onStarted={setJobId} />}
    </div>
  )
}
