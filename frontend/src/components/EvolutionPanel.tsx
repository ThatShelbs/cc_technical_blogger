import { Sparkles, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { errorText } from '../api/client'
import { useEvolutionMutations, usePersonaEvolution } from '../api/hooks'
import type { EvolutionOut, PersonaEvolutionOut } from '../api/types.gen'
import { KIND_LABEL, outcomeInfo, percent } from '../lib/stages'
import { EvolutionDialog } from './EvolutionDialog'
import { Badge, Button, Card, Notice, Spinner } from './ui'

const STATE_LABEL: Record<string, string> = {
  analyzing: 'Analyzing…',
  pending: 'To review',
  applied: 'Applied',
  clean: 'Nothing to change',
  dismissed: 'Dismissed',
  error: 'Failed',
}

/** How much of each published post's generated text the author changed, oldest first: it should fall as the persona learns. */
function EditRateTrend({ points }: { points: PersonaEvolutionOut['edit_rates'] }) {
  if (!points.length) return <p className="text-sm text-muted">Publish a generated post to start the trend.</p>
  const recent = points.slice(-12)
  return (
    <div>
      <ol className="flex h-28 items-end gap-1.5" aria-label="Share of generated text changed per published post">
        {recent.map((point, i) => (
          <li
            key={`${point.project_id}-${i}`}
            className="flex h-full flex-1 flex-col items-center justify-end gap-1"
            title={`${point.title}: ${percent(point.edit_rate)}`}
          >
            <span className="text-[10px] text-muted">{percent(point.edit_rate)}</span>
            <span className="w-full max-w-8 rounded-t bg-accent" style={{ height: `${Math.max(3, point.edit_rate * 100)}%` }} />
          </li>
        ))}
      </ol>
      <p className="mt-2 text-xs text-muted">Oldest on the left. Lower is better: the persona needed fewer edits.</p>
    </div>
  )
}

/** The persona's evolution: proposals from published posts, the playbook of what works, and the edit-rate trend. */
export function EvolutionPanel({ personaId }: { personaId: number }) {
  const { data, isLoading, error } = usePersonaEvolution(personaId)
  const { forgetPlaybook } = useEvolutionMutations(personaId)
  const [reviewing, setReviewing] = useState<EvolutionOut | null>(null)
  if (isLoading) return <Spinner />
  if (error || !data) return <Notice tone="error">{error ? errorText(error) : 'Could not load the evolution.'}</Notice>
  const pending = data.evolutions.filter((e) => e.state === 'pending')
  const history = data.evolutions.filter((e) => e.state !== 'pending')

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card className="h-fit space-y-4 lg:col-span-2">
        <div>
          <h2 className="text-lg font-bold">Waiting for review</h2>
          <p className="text-sm text-muted">
            When you publish a post, Proseferno compares your version with what it generated and suggests small changes. When a post does well, it works out the
            secret sauce. Nothing changes until you apply it.
          </p>
        </div>
        {pending.length === 0 ? (
          <p className="text-sm text-muted">Nothing to review. Mark a post Published, or rate one Good traction or Viral.</p>
        ) : (
          <ul className="space-y-2">
            {pending.map((evolution) => (
              <li key={evolution.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line p-3 text-sm">
                <div className="min-w-0">
                  <p className="font-semibold">
                    {KIND_LABEL[evolution.kind]}: {evolution.project_title}
                  </p>
                  <p className="text-muted">{evolution.summary}</p>
                </div>
                <Button size="sm" variant="flame" icon={<Sparkles className="size-4" />} onClick={() => setReviewing(evolution)}>
                  Review {evolution.items.length}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="h-fit space-y-4">
        <div>
          <h2 className="text-lg font-bold">Edits needed per post</h2>
          <p className="text-sm text-muted">Share of the generated text you changed before publishing.</p>
        </div>
        <EditRateTrend points={data.edit_rates} />
      </Card>

      <Card className="h-fit space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold">Playbook</h2>
            <p className="text-sm text-muted">Moves from your best-received posts. Every post and the next voice profile use them where they fit.</p>
          </div>
          {data.playbook.length > 0 && (
            <Button size="sm" variant="ghost" className="shrink-0" onClick={() => confirm('Forget the whole playbook?') && forgetPlaybook.mutate(undefined)}>
              Forget all
            </Button>
          )}
        </div>
        {data.playbook.length === 0 ? (
          <p className="text-sm text-muted">Nothing yet. Rate a published post Good traction or Viral and apply its secret sauce.</p>
        ) : (
          <ul className="space-y-2">
            {data.playbook.map((entry, index) => {
              const outcome = outcomeInfo(entry.outcome)
              return (
                <li key={`${entry.text}-${index}`} className="flex items-start gap-3 rounded-xl border border-line p-3 text-sm">
                  <div className="min-w-0 flex-1 space-y-1">
                    <p className="break-words">{entry.text}</p>
                    <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
                      {outcome && <Badge tone={outcome.tone}>{outcome.label}</Badge>}
                      {entry.title}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="rounded-md p-1 text-muted hover:bg-danger-soft hover:text-danger"
                    aria-label="Forget this playbook entry"
                    onClick={() => forgetPlaybook.mutate(index)}
                  >
                    <X className="size-4" />
                  </button>
                </li>
              )
            })}
          </ul>
        )}
        {forgetPlaybook.error && <Notice tone="error">{errorText(forgetPlaybook.error)}</Notice>}
      </Card>

      {history.length > 0 && (
        <Card className="h-fit space-y-3 lg:col-span-2">
          <h2 className="text-lg font-bold">History</h2>
          <ul className="space-y-2">
            {history.map((evolution) => (
              <li key={evolution.id} className="space-y-1 rounded-xl border border-line p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold">
                    {KIND_LABEL[evolution.kind]}:{' '}
                    {evolution.project_id ? (
                      <Link to={`/projects/${evolution.project_id}`} className="hover:underline">
                        {evolution.project_title}
                      </Link>
                    ) : (
                      evolution.project_title
                    )}
                  </p>
                  <span className="flex items-center gap-1.5">
                    {evolution.edit_rate != null && <span className="text-xs text-muted">{percent(evolution.edit_rate)} edited</span>}
                    <Badge tone={evolution.state === 'applied' ? 'success' : evolution.state === 'error' ? 'danger' : 'neutral'}>
                      {STATE_LABEL[evolution.state] ?? evolution.state}
                    </Badge>
                  </span>
                </div>
                {evolution.summary && <p className="text-muted">{evolution.summary}</p>}
                {evolution.state === 'error' && evolution.error && <p className="text-danger">{evolution.error}</p>}
                {evolution.state === 'applied' && (
                  <ul className="list-disc pl-5 text-muted">
                    {evolution.items
                      .filter((i) => i.applied)
                      .map((i) => (
                        <li key={i.id}>{i.change}</li>
                      ))}
                  </ul>
                )}
                {evolution.applied_version && <p className="text-xs text-muted">Saved as voice profile v{evolution.applied_version}.</p>}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {reviewing && <EvolutionDialog key={reviewing.id} evolution={reviewing} personaId={personaId} open onClose={() => setReviewing(null)} />}
    </div>
  )
}
