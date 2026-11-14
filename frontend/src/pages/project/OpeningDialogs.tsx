import { Laugh, Lightbulb } from 'lucide-react'

import type { OpeningInfoOut, OpeningStyleOut } from '../../api/types.gen'
import { Badge, Button, Dialog, Select } from '../../components/ui'
import { cx } from '../../lib/cx'
import { JUDGES, rankPitches } from '../../lib/opening'

/**
 * Every concept the opening room pitched, ranked by the panel: four judges' scores and notes, a pick to build, the
 * next best idea, or a fresh round in one style. Building a stored pitch needs no new pitching or judging.
 */
export function OpeningIdeasDialog({
  open,
  onClose,
  opening,
  styles,
  onPick,
  onNext,
  onStyle,
  onMemeIdeas,
}: {
  open: boolean
  onClose: () => void
  opening: OpeningInfoOut
  styles: OpeningStyleOut[]
  onPick: (index: number) => void
  onNext: () => void
  onStyle: (id: string) => void
  /** The opening meme's own joke pitches, when the opening is a meme */
  onMemeIdeas?: () => void
}) {
  const ranked = rankPitches(opening.pitches)
  return (
    <Dialog open={open} onClose={onClose} title="Opening image ideas" wide>
      <p className="mb-2 text-sm text-muted">
        Claude pitched these openings{opening.mode === 'auto' ? ' across styles' : ` as ${styles.find((s) => s.id === opening.mode)?.label ?? 'one style'}`},
        and a panel of four judges scored each one from 1 to 10. Pick any idea to build it.
      </p>
      {opening.summary && <p className="mb-4 text-sm italic">Panel: {opening.summary}</p>}
      <ul className="list-none space-y-3 pl-0">
        {ranked.map((pitch, rank) => (
          <li
            key={pitch.index}
            aria-label={`${pitch.style_label}: ${pitch.concept}`}
            className={cx('rounded-xl border p-3', pitch.current ? 'border-accent bg-sunken' : 'border-line', pitch.ruled_out && 'opacity-70')}
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="accent">{pitch.style_label}</Badge>
              {rank === 0 && !pitch.ruled_out && <Badge>Panel pick</Badge>}
              {pitch.current ? <Badge>Showing now</Badge> : pitch.tried ? <Badge>Tried</Badge> : null}
              {pitch.ruled_out && <Badge>Ruled out</Badge>}
              <span className="ml-auto text-sm font-semibold" title="Total of the four judges' scores">
                {pitch.total}/40
              </span>
            </div>
            {pitch.hook && <p className="mt-2 text-sm font-semibold">{pitch.hook}</p>}
            <p className="mt-1 text-sm">{pitch.concept}</p>
            <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
              {JUDGES.map((judge) => (
                <div key={judge.key} className="flex gap-1" title={judge.hint}>
                  <dt>{judge.label}</dt>
                  <dd className="font-semibold text-fg">{pitch.scores[judge.key] ?? '–'}</dd>
                </div>
              ))}
            </dl>
            {pitch.note && <p className="mt-1 text-xs text-muted">{pitch.note}</p>}
            {!pitch.current && (
              <Button size="sm" variant="secondary" className="mt-3" onClick={() => onPick(pitch.index)}>
                Use this one
              </Button>
            )}
          </li>
        ))}
      </ul>
      <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-line pt-4">
        <Button size="sm" variant="secondary" icon={<Lightbulb className="size-4" />} onClick={onNext}>
          {opening.ideas_left ? 'Next best idea' : 'Pitch new ideas'}
        </Button>
        <Select
          aria-label="Pitch new ideas in one style"
          title="Pitch four new ideas in this style; the panel judges them again"
          className="h-8 w-56 max-w-full text-sm"
          value=""
          onChange={(e) => e.target.value && onStyle(e.target.value)}
        >
          <option value="">Try as…</option>
          {styles.map((s) => (
            <option key={s.id} value={s.id} title={s.summary}>
              {s.label}
            </option>
          ))}
        </Select>
        {onMemeIdeas && (
          <Button size="sm" variant="ghost" icon={<Laugh className="size-4" />} onClick={onMemeIdeas}>
            Other jokes for this meme
          </Button>
        )}
      </div>
    </Dialog>
  )
}
