import { useQueryClient } from '@tanstack/react-query'
import { Flame, History, PencilLine, RefreshCw } from 'lucide-react'
import { useState } from 'react'

import { ApiError, errorText } from '../api/client'
import { keys, usePersona, usePersonaMutations, useSaveVoiceSoul, useVoiceSoul, useVoiceSoulVersions } from '../api/hooks'
import { useJob } from '../api/useJob'
import { Markdown } from './Article'
import { Badge, Button, Card, EmptyState, Notice, ProgressBar, Select, Textarea } from './ui'

const STAT_LABELS: [string, string, (v: number) => string][] = [
  ['avg_sentence_words', 'Words per sentence', (v) => v.toFixed(1)],
  ['avg_paragraph_words', 'Words per paragraph', (v) => v.toFixed(0)],
  ['short_paragraph_ratio', 'One-sentence paragraphs', (v) => `${Math.round(v * 100)}%`],
  ['flesch_reading_ease', 'Reading ease', (v) => v.toFixed(0)],
  ['words_per_heading', 'Words per heading', (v) => v.toFixed(0)],
  ['words_per_image', 'Words per image', (v) => v.toFixed(0)],
]

export function VoiceSoulPanel({ personaId, onGenerated }: { personaId: number; onGenerated?: () => void }) {
  const qc = useQueryClient()
  const persona = usePersona(personaId)
  const [version, setVersion] = useState<number | undefined>()
  const soul = useVoiceSoul(personaId, version)
  const versions = useVoiceSoulVersions(personaId)
  const mutations = usePersonaMutations()
  const save = useSaveVoiceSoul(personaId)
  const [jobId, setJobId] = useState<string | null>(null)
  const [editing, setEditing] = useState<string | null>(null)
  const runningJobId = jobId ?? persona.data?.active_job_id ?? null

  const job = useJob(runningJobId, (state) => {
    setJobId(null)
    void qc.invalidateQueries({ queryKey: ['personas'] })
    void qc.invalidateQueries({ queryKey: keys.voiceSoulVersions(personaId) })
    setVersion(undefined)
    if (state.status === 'succeeded') onGenerated?.()
  })

  const generate = () =>
    mutations.generateVoiceSoul.mutate(personaId, {
      onSuccess: (created) => setJobId(created.id),
    })

  const ownSamples = persona.data?.own_samples ?? 0
  const missing = soul.error instanceof ApiError && soul.error.status === 404
  const running = !!runningJobId && job.status !== 'succeeded' && job.status !== 'failed'

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
            <Button variant="flame" size="lg" onClick={generate} disabled={ownSamples === 0} loading={mutations.generateVoiceSoul.isPending}>
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
          <p className="text-sm text-muted">Saving creates a new version; older versions stay in the history.</p>
          <Textarea value={editing} onChange={(e) => setEditing(e.target.value)} rows={24} className="font-mono text-sm" aria-label="Voice soul markdown" />
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
              {soul.data.edited_by_user && <Badge>Edited by you</Badge>}
              <Badge>
                {soul.data.sample_count} sample{soul.data.sample_count === 1 ? '' : 's'}
              </Badge>
              {soul.data.best_practices && <Badge>Includes web research</Badge>}
            </div>
            <div className="flex flex-wrap gap-2">
              {versions.data && versions.data.length > 1 && (
                <label className="flex items-center gap-2 text-sm">
                  <History className="size-4 text-muted" aria-hidden />
                  <span className="sr-only">Version</span>
                  <Select className="h-9 w-auto" value={version ?? ''} onChange={(e) => setVersion(e.target.value ? Number(e.target.value) : undefined)}>
                    <option value="">Latest</option>
                    {versions.data.map((v) => (
                      <option key={v.id} value={v.version}>
                        v{v.version} · {new Date(v.created_at).toLocaleDateString()}
                        {v.edited_by_user ? ' (edited)' : ''}
                      </option>
                    ))}
                  </Select>
                </label>
              )}
              <Button variant="secondary" size="sm" icon={<PencilLine className="size-4" />} onClick={() => setEditing(soul.data.markdown)}>
                Edit
              </Button>
              <Button size="sm" icon={<RefreshCw className="size-4" />} onClick={generate} loading={mutations.generateVoiceSoul.isPending}>
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
    </div>
  )
}
