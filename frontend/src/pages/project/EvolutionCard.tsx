import { GitCompare, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { errorText } from '../../api/client'
import { useBaselineDiff, useEvolutionMutations } from '../../api/hooks'
import type { EvolutionOut, ProjectOut } from '../../api/types.gen'
import { EvolutionDialog } from '../../components/EvolutionDialog'
import { Badge, Button, Card, Dialog, Notice, Spinner } from '../../components/ui'
import { KIND_LABEL, percent, SAUCE_OUTCOMES, type Outcome } from '../../lib/stages'

/** The generated text against the current one: cuts struck through, additions highlighted. */
export function BaselineDiffDialog({ projectId, open, onClose }: { projectId: number; open: boolean; onClose: () => void }) {
  const { data, isLoading, error } = useBaselineDiff(projectId, open)
  return (
    <Dialog open={open} onClose={onClose} title="Generated vs. your version" wide>
      {isLoading && <Spinner />}
      {error && <Notice tone="error">{errorText(error)}</Notice>}
      {data && (
        <div className="space-y-3">
          <p className="text-sm text-muted">
            You changed {percent(data.edit_rate)} of the generated text. <del className="rounded bg-danger-soft px-0.5 text-danger">Struck through</del> is what
            you cut; <ins className="rounded bg-success-soft px-0.5 text-success no-underline">highlighted</ins> is what you added.
          </p>
          <div className="max-h-[60vh] overflow-y-auto rounded-xl border border-line bg-sunken p-4 font-mono text-xs leading-relaxed whitespace-pre-wrap">
            {data.segments.map((segment, i) =>
              segment.op === 'insert' ? (
                <ins key={i} className="rounded bg-success-soft text-success no-underline">
                  {segment.text}
                </ins>
              ) : segment.op === 'delete' ? (
                <del key={i} className="rounded bg-danger-soft text-danger">
                  {segment.text}
                </del>
              ) : (
                <span key={i}>{segment.text}</span>
              ),
            )}
          </div>
        </div>
      )}
    </Dialog>
  )
}

function EvolutionRow({ evolution, project, onReview }: { evolution: EvolutionOut; project: ProjectOut; onReview: () => void }) {
  const { analyze } = useEvolutionMutations(project.persona_id, project.id)
  const again = (
    <Button size="sm" variant="ghost" loading={analyze.isPending} onClick={() => analyze.mutate(evolution.kind as 'edits' | 'secret_sauce')}>
      Analyze again
    </Button>
  )
  const applied = evolution.items.filter((i) => i.applied).length
  return (
    <li className="space-y-1.5 rounded-xl border border-line p-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <p className="font-semibold">{KIND_LABEL[evolution.kind] ?? evolution.kind}</p>
        {evolution.state === 'pending' && <Badge tone="accent">To review</Badge>}
        {evolution.state === 'applied' && <Badge tone="success">Applied</Badge>}
        {evolution.state === 'clean' && <Badge tone="success">Nothing to change</Badge>}
        {evolution.state === 'dismissed' && <Badge>Dismissed</Badge>}
        {evolution.state === 'error' && <Badge tone="danger">Failed</Badge>}
      </div>
      {evolution.state === 'analyzing' && <Spinner label={evolution.kind === 'edits' ? 'Reading your edits…' : 'Working out what made it land…'} />}
      {evolution.state !== 'analyzing' && evolution.summary && <p className="text-muted">{evolution.summary}</p>}
      {evolution.state === 'error' && <p className="text-danger">{evolution.error}</p>}
      {evolution.state === 'pending' && (
        <Button size="sm" variant="flame" icon={<Sparkles className="size-4" />} onClick={onReview}>
          Review {evolution.items.length} suggestion{evolution.items.length === 1 ? '' : 's'}
        </Button>
      )}
      {evolution.state === 'applied' && (
        <p className="text-xs text-muted">
          {applied} change{applied === 1 ? '' : 's'} kept ·{' '}
          {evolution.applied_version && (
            <>
              <Link to={`/personas/${project.persona_id}?tab=voice`} className="font-semibold text-accent hover:underline">
                voice profile v{evolution.applied_version}
              </Link>{' '}
              ·{' '}
            </>
          )}
          <Link to={`/personas/${project.persona_id}?tab=evolution`} className="font-semibold text-accent hover:underline">
            See the persona&rsquo;s evolution
          </Link>
        </p>
      )}
      {['applied', 'clean', 'dismissed', 'error'].includes(evolution.state) && project.stage === 'published' && again}
      {analyze.error && <Notice tone="error">{errorText(analyze.error)}</Notice>}
    </li>
  )
}

/**
 * Teach the persona from this post: how much of the generated text the author changed, and the
 * proposals learned when it was published (from the edits) or did well (its secret sauce).
 */
export function EvolutionCard({ project }: { project: ProjectOut }) {
  const [comparing, setComparing] = useState(false)
  const [reviewing, setReviewing] = useState<EvolutionOut | null>(null)
  const { analyze } = useEvolutionMutations(project.persona_id, project.id)
  // Newest proposal of each kind.
  const latest = new Map<string, EvolutionOut>()
  for (const e of project.evolutions) latest.set(e.kind, e)
  const published = project.stage === 'published'
  const hit = SAUCE_OUTCOMES.includes(project.outcome as Outcome)
  if (!project.has_baseline && !project.evolutions.length && !published) return null

  return (
    <Card className="space-y-3">
      <h2 className="font-bold">Teach the persona</h2>
      {project.has_baseline && project.edit_rate != null ? (
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <p>
            You changed <span className="font-semibold">{percent(project.edit_rate)}</span> of the generated text.
          </p>
          <Button size="sm" variant="secondary" icon={<GitCompare className="size-4" />} onClick={() => setComparing(true)}>
            Compare
          </Button>
        </div>
      ) : (
        <p className="text-sm text-muted">This post has no generated text on record to compare with. Regenerate it to start tracking your edits.</p>
      )}
      {!published && (
        <p className="text-xs text-muted">
          Mark the post Published when it goes out: Proseferno compares your version with what it generated and suggests small changes to the persona, so the
          next post needs fewer edits. Rate it Good traction or Viral later to learn its secret sauce.
        </p>
      )}
      {latest.size > 0 && (
        <ul className="space-y-2">
          {[...latest.values()].map((evolution) => (
            <EvolutionRow key={evolution.id} evolution={evolution} project={project} onReview={() => setReviewing(evolution)} />
          ))}
        </ul>
      )}
      {published && project.has_baseline && !latest.has('edits') && (
        <Button size="sm" variant="secondary" loading={analyze.isPending && analyze.variables === 'edits'} onClick={() => analyze.mutate('edits')}>
          Learn from my edits
        </Button>
      )}
      {published && hit && !latest.has('secret_sauce') && (
        <Button
          size="sm"
          variant="secondary"
          loading={analyze.isPending && analyze.variables === 'secret_sauce'}
          onClick={() => analyze.mutate('secret_sauce')}
        >
          Find the secret sauce
        </Button>
      )}
      {analyze.error && <Notice tone="error">{errorText(analyze.error)}</Notice>}
      {comparing && <BaselineDiffDialog projectId={project.id} open onClose={() => setComparing(false)} />}
      {reviewing && (
        <EvolutionDialog
          key={reviewing.id}
          evolution={reviewing}
          personaId={project.persona_id}
          projectId={project.id}
          open
          onClose={() => setReviewing(null)}
        />
      )}
    </Card>
  )
}
