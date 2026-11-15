import { Bookmark, BookmarkCheck, NotebookPen, X } from 'lucide-react'
import { Link } from 'react-router'

import type { IdeaOut } from '../../api/types.gen'
import { Badge, Button, Card } from '../../components/ui'
import { cx } from '../../lib/cx'
import { LIFECYCLE_STEPS, SHELF_LIFE, stageOf, stepIndex } from '../../lib/ideas'

export function StageBadge({ idea }: { idea: IdeaOut }) {
  const stage = stageOf(idea.stage)
  return (
    <span title={stage.hint} className="inline-flex">
      <Badge tone={stage.tone}>{idea.stage_label}</Badge>
    </span>
  )
}

/** Prospective → Serious → Generated → Ready → Published, with the outcome named on the last step. */
export function LifecycleLine({ idea }: { idea: IdeaOut }) {
  const at = stepIndex(idea.stage)
  if (at === -1) return <p className="text-sm text-muted">Dismissed: it will not be suggested again. Bring it back to keep it.</p>
  return (
    <ol aria-label={`Lifecycle: ${idea.stage_label}`} className="flex flex-wrap items-center gap-1 text-xs">
      {LIFECYCLE_STEPS.map((step, i) => {
        const last = i === LIFECYCLE_STEPS.length - 1
        const label = last && at === i && idea.stage !== 'published' ? `Published · ${idea.stage_label}` : step.label
        return (
          <li key={step.id} className="flex items-center gap-1">
            <span
              aria-current={i === at ? 'step' : undefined}
              className={cx(
                'rounded-full px-2 py-0.5 font-semibold',
                i === at ? 'flame-button text-white' : i < at ? 'bg-accent-soft text-fg' : 'bg-surface-2 text-muted',
              )}
            >
              {label}
            </span>
            {!last && (
              <span className="text-muted" aria-hidden>
                →
              </span>
            )}
          </li>
        )
      })}
    </ol>
  )
}

export function IdeaCard({
  idea,
  onOpen,
  onState,
  showRank = true,
}: {
  idea: IdeaOut
  onOpen: () => void
  onState: (state: 'new' | 'saved' | 'dismissed') => void
  showRank?: boolean
}) {
  const saved = idea.state === 'saved'
  const used = idea.state === 'used'
  return (
    <Card className={cx('flex flex-col gap-2', idea.state === 'dismissed' && 'opacity-70')}>
      <div className="flex flex-wrap items-center gap-1.5">
        {showRank && idea.approach !== 'own' && <Badge tone="flame">#{idea.rank}</Badge>}
        {idea.stage !== 'prospective' && <StageBadge idea={idea} />}
        <Badge tone="accent">{idea.approach_label}</Badge>
        {idea.shelf_life !== 'evergreen' && !used && <Badge>{SHELF_LIFE[idea.shelf_life] ?? idea.shelf_life}</Badge>}
        <span className="ml-auto text-xs text-muted">{idea.theme}</span>
      </div>
      <button type="button" onClick={onOpen} className="text-left text-lg leading-snug font-bold hover:underline">
        {idea.title}
      </button>
      <p className="line-clamp-3 text-sm text-muted">{idea.brief}</p>
      {idea.note ? (
        <p className="line-clamp-2 flex items-start gap-1.5 text-sm">
          <NotebookPen className="mt-0.5 size-3.5 shrink-0 text-accent" aria-label="Your note" />
          {idea.note}
        </p>
      ) : (
        idea.why_now && <p className="line-clamp-2 text-sm">{idea.why_now}</p>
      )}
      <div className="mt-auto flex items-center gap-2 pt-2">
        <Button size="sm" variant="secondary" onClick={onOpen}>
          {used ? 'Details' : 'Outline & write'}
        </Button>
        {used && idea.project_id ? (
          <Link to={`/projects/${idea.project_id}`} className="text-sm font-semibold text-accent hover:underline">
            Open the post
          </Link>
        ) : (
          <span className="ml-auto flex items-center gap-1">
            <button
              type="button"
              className="rounded-md p-1.5 text-muted hover:bg-surface-2 hover:text-fg"
              aria-label={saved ? `Remove ${idea.title} from saved` : `Save ${idea.title}`}
              aria-pressed={saved}
              onClick={() => onState(saved ? 'new' : 'saved')}
            >
              {saved ? <BookmarkCheck className="size-4 text-accent" /> : <Bookmark className="size-4" />}
            </button>
            <button
              type="button"
              className="rounded-md p-1.5 text-muted hover:bg-danger-soft hover:text-danger"
              aria-label={idea.state === 'dismissed' ? `Bring back ${idea.title}` : `Dismiss ${idea.title}`}
              onClick={() => onState(idea.state === 'dismissed' ? 'new' : 'dismissed')}
            >
              <X className="size-4" />
            </button>
          </span>
        )}
      </div>
    </Card>
  )
}
