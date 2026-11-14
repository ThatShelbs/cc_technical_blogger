import type { JobState, Lane } from '../../../api/useJob'
import { Article } from '../../../components/Article'
import { Card, ProgressBar } from '../../../components/ui'
import { SIDE_NAME } from '../../../lib/ab'

/** Both posts of an A/B test being written at once, side by side (stacked on narrow screens). */
export function ABGenerationView({ job }: { job: JobState }) {
  return (
    <div className="space-y-4">
      <Card className="space-y-2">
        <h2 className="font-bold">Writing two versions of your post</h2>
        <p className="text-sm text-muted">
          One is written exactly as your persona is set up; the other with its settings, voice emphasis and image style nudged. You will not be told which is
          which until you pick a favorite.
        </p>
        <ProgressBar value={job.progress} label="A/B test progress" />
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        {(['left', 'right'] as Lane[]).map((lane) => (
          <LaneCard key={lane} name={SIDE_NAME[lane]} state={job.lanes[lane]} />
        ))}
      </div>
    </div>
  )
}

function LaneCard({ name, state }: { name: string; state: JobState | undefined }) {
  return (
    <Card padded={false} className="min-w-0 space-y-4 p-5 sm:p-8" aria-live="polite" aria-busy="true" aria-label={name}>
      <div className="space-y-2">
        <h3 className="font-bold">{name}</h3>
        <ProgressBar value={state?.progress ?? 0} label={`${name} progress`} />
        <p className="text-xs text-muted">{state?.message || 'Waiting to start'}</p>
      </div>
      {state?.draft ? (
        <div className="max-h-[70vh] overflow-auto">
          <Article
            markdown={state.draft}
            renderImage={(slot) => (
              <div className="my-4 flex aspect-[16/7] items-center justify-center rounded-xl border border-dashed border-line bg-sunken font-sans text-xs text-muted">
                Image “{slot}” comes after the text
              </div>
            )}
          />
        </div>
      ) : (
        <div className="flex min-h-48 items-center justify-center">
          <img src="/logo-mark.svg" alt="" className="size-14 animate-pulse" />
        </div>
      )}
    </Card>
  )
}
