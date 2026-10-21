import { Check, Loader2 } from 'lucide-react'

import type { JobState } from '../../api/useJob'
import { Article } from '../../components/Article'
import { Card, ProgressBar } from '../../components/ui'
import { cx } from '../../lib/cx'

const STEPS = [
  { label: 'Plan', until: 0.12 },
  { label: 'Draft', until: 0.45 },
  { label: 'Voice edit', until: 0.7 },
  { label: 'Images', until: 0.99 },
  { label: 'Ready', until: 1.01 },
]

export function GenerationView({ job }: { job: JobState }) {
  const active = STEPS.findIndex((s) => job.progress < s.until)
  const critique = job.critique
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
      <Card padded={false} className="p-6 sm:p-10" aria-live="polite" aria-busy="true">
        {job.draft ? (
          <Article
            markdown={job.draft}
            renderImage={(slot) => (
              <div className="my-6 flex aspect-[16/7] items-center justify-center rounded-xl border border-dashed border-line bg-sunken font-sans text-sm text-muted">
                Image “{slot}” is created after the text
              </div>
            )}
          />
        ) : (
          <div className="flex min-h-80 flex-col items-center justify-center gap-4 text-center">
            <img src="/logo-mark.svg" alt="" className="size-20 animate-pulse" />
            <p className="text-lg font-semibold">{job.message || 'Warming up the robot…'}</p>
            <p className="max-w-sm text-sm text-muted">Your draft will appear here as it is written.</p>
          </div>
        )}
      </Card>

      <div className="space-y-4">
        <Card className="space-y-4">
          <h2 className="font-bold">Writing your post</h2>
          <ProgressBar value={job.progress} label="Post progress" />
          <p className="text-sm text-muted">{job.message}</p>
          <ol className="space-y-2">
            {STEPS.map((step, i) => (
              <li key={step.label} className="flex items-center gap-2 text-sm">
                {i < active || job.status === 'succeeded' ? (
                  <Check className="size-4 text-success" aria-hidden />
                ) : i === active ? (
                  <Loader2 className="size-4 animate-spin text-accent" aria-hidden />
                ) : (
                  <span className="size-4 rounded-full border border-line" aria-hidden />
                )}
                <span className={cx(i === active ? 'font-semibold' : i > active ? 'text-muted' : '')}>{step.label}</span>
              </li>
            ))}
          </ol>
        </Card>
        {critique && (
          <Card className="space-y-2">
            <h2 className="font-bold">Editor’s notes</h2>
            <p className="text-sm">
              Voice match <strong>{critique.voice}/10</strong> · overall <strong>{critique.overall}/10</strong>
            </p>
            <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
              {critique.revision_instructions.slice(0, 4).map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </div>
  )
}
