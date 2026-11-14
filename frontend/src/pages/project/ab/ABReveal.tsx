import { FlaskConical } from 'lucide-react'
import { useState } from 'react'

import { errorText } from '../../../api/client'
import { useABTest, useABTestMutations } from '../../../api/hooks'
import type { ABTestOut } from '../../../api/types.gen'
import { useJob } from '../../../api/useJob'
import { Badge, Button, Card, Dialog, Notice, ProgressBar } from '../../../components/ui'
import { SIDE_NAME, TWEAK_GROUPS, type ABSide } from '../../../lib/ab'

/** After the choice: which post was which, and (when the challenger's choices were kept) what to adopt into the persona. */
export function ABReveal({ projectId, testId }: { projectId: number; testId: number }) {
  const { data: test } = useABTest(testId)
  const { adopt, refresh } = useABTestMutations(projectId, testId)
  const [open, setOpen] = useState(false)
  if (!test || test.status !== 'decided') return null

  const side = SIDE_NAME[(test.winner_side ?? 'left') as ABSide]
  const challengerWon = test.winner === 'challenger'
  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <FlaskConical className="size-5 text-accent" aria-hidden />
        <h2 className="font-bold">A/B test: {challengerWon ? `${side} was the tweaked version` : `${side} was your persona as it is`}</h2>
      </div>
      <p className="text-sm">
        {challengerWon
          ? 'You preferred the version with nudged settings. Make what worked part of your persona?'
          : 'Your current settings won. Some of the parts you took came from the tweaked version; you can keep those settings too.'}
      </p>
      {adopt.error && <Notice tone="error">{errorText(adopt.error)}</Notice>}
      <div className="flex flex-wrap gap-2">
        <Button variant="flame" size="sm" onClick={() => setOpen(true)}>
          Review the changes
        </Button>
        <Button variant="ghost" size="sm" loading={adopt.isPending} onClick={() => adopt.mutate([], { onSuccess: refresh })}>
          Keep my settings
        </Button>
      </div>
      {open && <AdoptDialog test={test} projectId={projectId} onClose={() => setOpen(false)} />}
    </Card>
  )
}

export function AdoptDialog({ test, projectId, onClose }: { test: ABTestOut; projectId: number; onClose: () => void }) {
  const { adopt, refresh } = useABTestMutations(projectId, test.id)
  const [selected, setSelected] = useState<Set<string>>(() => new Set(test.tweaks.filter((t) => t.suggested).map((t) => t.id)))
  const [jobId, setJobId] = useState<string | null>(null)
  const job = useJob(jobId, (state) => {
    refresh()
    if (state.status === 'succeeded') onClose()
  })
  const running = !!jobId && job.status !== 'succeeded' && job.status !== 'failed'
  const toggle = (id: string) =>
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  const groups = TWEAK_GROUPS.map((group) => ({ group, tweaks: test.tweaks.filter((t) => t.group === group) })).filter((g) => g.tweaks.length)
  const voice = test.tweaks.some((t) => selected.has(t.id) && ['Voice', 'Principles', 'Title'].includes(t.group))
  const submit = () =>
    adopt.mutate([...selected], {
      onSuccess: (data) => {
        if (data.job && data.job.status !== 'succeeded') setJobId(data.job.id)
        else onClose()
      },
    })

  return (
    <Dialog open onClose={onClose} title="Adopt what won the A/B test" wide>
      <div className="space-y-4">
        <p className="text-sm text-muted">
          Ticked changes are what the version you kept was written with. Adopt all of them, or only the ones you think made the difference.
        </p>
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" disabled={running} onClick={() => setSelected(new Set(test.tweaks.map((t) => t.id)))}>
            Select all
          </Button>
          <Button size="sm" variant="ghost" disabled={running} onClick={() => setSelected(new Set())}>
            Select none
          </Button>
        </div>
        {groups.map(({ group, tweaks }) => (
          <section key={group} className="space-y-2">
            <h3 className="text-sm font-bold">{group}</h3>
            <ul className="space-y-2">
              {tweaks.map((tweak) => (
                <li key={tweak.id}>
                  <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-line p-3 text-sm hover:bg-surface-2">
                    <input
                      type="checkbox"
                      className="mt-1 size-4 accent-[var(--app-accent)]"
                      checked={selected.has(tweak.id)}
                      onChange={() => toggle(tweak.id)}
                      disabled={running}
                    />
                    <span className="min-w-0 flex-1 space-y-1">
                      <span className="flex flex-wrap items-center gap-1.5">
                        <span className="font-semibold">{tweak.label}</span>
                        {tweak.suggested && <Badge tone="accent">In the post you kept</Badge>}
                      </span>
                      <span className="block break-words text-muted">
                        {tweak.before} → <span className="text-fg">{tweak.after}</span>
                      </span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          </section>
        ))}
        <p className="text-xs text-muted">
          Settings, formula and image style become your persona's defaults. Example posts are favored when the writer picks examples. Voice, principle and title
          changes are written into a new voice profile version, so you can go back any time.
        </p>
        {running && (
          <div className="space-y-1">
            <ProgressBar value={job.progress} label="Updating the voice profile" />
            <p className="text-xs text-muted">{job.message || 'Starting'}</p>
          </div>
        )}
        {job.status === 'failed' && <Notice tone="error">{job.error || 'Could not update the voice profile.'}</Notice>}
        {adopt.error && <Notice tone="error">{errorText(adopt.error)}</Notice>}
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="ghost" disabled={running} onClick={onClose}>
            Not now
          </Button>
          <Button variant="flame" disabled={running} loading={adopt.isPending || running} onClick={submit}>
            {selected.size === 0
              ? 'Keep my settings'
              : `Adopt ${selected.size} change${selected.size === 1 ? '' : 's'}${voice ? ' (new voice profile version)' : ''}`}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
