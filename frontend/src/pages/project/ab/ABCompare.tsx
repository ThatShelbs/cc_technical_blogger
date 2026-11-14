import { Trophy } from 'lucide-react'
import { useState } from 'react'

import { errorText } from '../../../api/client'
import { useABTest, useABTestMutations } from '../../../api/hooks'
import type { ABVariantOut, JobOut } from '../../../api/types.gen'
import { Article } from '../../../components/Article'
import { Button, Card, Field, Notice, Spinner, Textarea } from '../../../components/ui'
import { PARTS, SIDE_NAME, otherSide, type ABPart, type ABSide } from '../../../lib/ab'
import { cx } from '../../../lib/cx'

/**
 * The blind choice: both posts side by side (tabs on narrow screens), labeled only by position.
 * The author picks a winner, may take parts of the other post, and may add a note; nothing is refined before that.
 */
export function ABCompare({ projectId, testId, onStarted }: { projectId: number; testId: number; onStarted: (job: JobOut) => void }) {
  const { data: test, isLoading, error } = useABTest(testId)
  const { decide, discard, retry } = useABTestMutations(projectId, testId)
  const [winner, setWinner] = useState<ABSide | null>(null)
  const [take, setTake] = useState<Set<ABPart>>(new Set())
  const [notes, setNotes] = useState('')
  const [tab, setTab] = useState<ABSide>('left')

  if (isLoading) return <Spinner />
  if (error || !test) return <Notice tone="error">{error ? errorText(error) : 'A/B test not found.'}</Notice>

  if (test.status === 'error') {
    return (
      <Card className="space-y-3">
        <Notice tone="error" title="One of the two posts could not be written">
          {test.error}
        </Notice>
        {(retry.error || discard.error) && <Notice tone="error">{errorText(retry.error ?? discard.error)}</Notice>}
        <div className="flex flex-wrap gap-2">
          <Button variant="flame" loading={retry.isPending} onClick={() => retry.mutate(undefined, { onSuccess: onStarted })}>
            Try again
          </Button>
          <Button variant="ghost" loading={discard.isPending} onClick={() => discard.mutate()}>
            Discard the A/B test
          </Button>
        </div>
      </Card>
    )
  }

  const toggle = (part: ABPart) =>
    setTake((current) => {
      const next = new Set(current)
      if (next.has(part)) next.delete(part)
      else next.add(part)
      return next
    })
  const loser = winner ? otherSide(winner) : null
  const submit = () => {
    if (!winner) return
    decide.mutate({ winner, take: PARTS.map((p) => p.id).filter((p) => take.has(p)), notes: notes.trim() }, { onSuccess: onStarted })
  }

  return (
    <div className="space-y-6">
      <Card className="space-y-2">
        <h2 className="font-bold">Which post do you like better?</h2>
        <p className="text-sm text-muted">
          One was written as your persona is set up today; the other with its settings nudged. Read both, pick a favorite, and take any parts you liked from the
          other one. You will see which was which afterwards.
        </p>
      </Card>

      <div className="flex gap-1 lg:hidden" role="tablist" aria-label="Posts">
        {(['left', 'right'] as ABSide[]).map((side) => (
          <button
            key={side}
            type="button"
            role="tab"
            aria-selected={tab === side}
            onClick={() => setTab(side)}
            className={cx('flex-1 rounded-lg px-3 py-2 text-sm font-semibold', tab === side ? 'bg-accent-soft' : 'text-muted hover:bg-surface-2')}
          >
            {SIDE_NAME[side]}
          </button>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {[test.left, test.right].map(
          (post) =>
            post && (
              <VariantColumn
                key={post.side}
                post={post}
                chosen={winner === post.side}
                hiddenOnSmall={tab !== post.side}
                onPick={() => setWinner(post.side as ABSide)}
              />
            ),
        )}
      </div>

      <Card className="space-y-4">
        {winner && loser ? (
          <>
            <h2 className="font-bold">
              {SIDE_NAME[winner]} wins. Anything to take from {SIDE_NAME[loser]}?
            </h2>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {PARTS.map((part) => (
                <label key={part.id} className="flex cursor-pointer items-start gap-3 rounded-xl border border-line p-3 text-sm hover:bg-surface-2">
                  <input type="checkbox" className="mt-1 size-4 accent-[var(--app-accent)]" checked={take.has(part.id)} onChange={() => toggle(part.id)} />
                  <span>
                    <span className="block font-semibold">{part.label}</span>
                    <span className="block text-muted">{part.hint}</span>
                  </span>
                </label>
              ))}
            </div>
            <Field label="Anything else to blend? (optional)" hint={`Applied as a tweak that can see ${SIDE_NAME[loser]}.`} htmlFor="ab-notes">
              <Textarea
                id="ab-notes"
                rows={3}
                maxLength={4000}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder={`Use the code example from ${SIDE_NAME[loser]} in the second section.`}
              />
            </Field>
            <p className="text-xs text-muted">{SIDE_NAME[loser]} is deleted once your post is ready.</p>
          </>
        ) : (
          <p className="text-sm text-muted">Pick the post you like better to continue.</p>
        )}
        {(decide.error || discard.error) && <Notice tone="error">{errorText(decide.error ?? discard.error)}</Notice>}
        <div className="flex flex-wrap justify-between gap-2">
          <Button
            variant="ghost"
            loading={discard.isPending}
            onClick={() => {
              if (confirm('Discard both posts? Your post stays as it was before the A/B test.')) discard.mutate()
            }}
          >
            Discard the A/B test
          </Button>
          <Button variant="flame" icon={<Trophy className="size-4" />} disabled={!winner} loading={decide.isPending} onClick={submit}>
            {winner ? `Keep ${SIDE_NAME[winner]}${take.size || notes.trim() ? ' with the blend' : ''}` : 'Pick a winner'}
          </Button>
        </div>
      </Card>
    </div>
  )
}

function VariantColumn({ post, chosen, hiddenOnSmall, onPick }: { post: ABVariantOut; chosen: boolean; hiddenOnSmall: boolean; onPick: () => void }) {
  const name = SIDE_NAME[post.side as ABSide]
  return (
    <Card
      padded={false}
      aria-label={name}
      className={cx('min-w-0 space-y-4 p-5 sm:p-8', chosen && 'ring-2 ring-[var(--app-accent)]', hiddenOnSmall && 'hidden lg:block')}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-bold">
          {name} <span className="text-sm font-normal text-muted">· {post.word_count.toLocaleString()} words</span>
        </h3>
        <Button size="sm" variant={chosen ? 'flame' : 'secondary'} aria-pressed={chosen} onClick={onPick}>
          {chosen ? 'Your pick' : `Pick ${name}`}
        </Button>
      </div>
      <Article markdown={post.markdown} images={post.images} />
    </Card>
  )
}
