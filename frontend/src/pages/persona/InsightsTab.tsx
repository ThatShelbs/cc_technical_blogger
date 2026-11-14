import { useQueryClient } from '@tanstack/react-query'
import { BarChart3, RefreshCw, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'

import { errorText } from '../../api/client'
import { keys, usePersonaInsights, useRefreshInsights } from '../../api/hooks'
import type { InsightsDigestOut, LessonItem, PersonaInsightsOut, TrackRecordOut } from '../../api/types.gen'
import { useJob } from '../../api/useJob'
import { Badge, Button, Card, EmptyState, Notice, Spinner, StatTile } from '../../components/ui'
import { cx } from '../../lib/cx'
import { outcomeInfo } from '../../lib/stages'
import { BarList } from './insights/BarList'
import { DumbbellChart } from './insights/DumbbellChart'
import { SankeyChart } from './insights/SankeyChart'
import { ScoreTrend } from './insights/ScoreTrend'
import { WaffleChart } from './insights/WaffleChart'

type OpenTab = (tab: 'samples' | 'voice') => void
const score = (value: number | null) => (value === null ? '–' : Math.round(value))
const plural = (n: number, word: string) => `${n.toLocaleString()} ${word}${n === 1 ? '' : 's'}`

function Section({ title, hint, aside, className, children }: { title: string; hint?: ReactNode; aside?: ReactNode; className?: string; children: ReactNode }) {
  return (
    <Card className={cx('h-fit min-w-0 space-y-3', className)}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-bold">{title}</h3>
          {hint && <p className="text-sm text-muted">{hint}</p>}
        </div>
        {aside && <span className="shrink-0 text-xs text-muted">{aside}</span>}
      </div>
      {children}
    </Card>
  )
}

const Chip = ({ children }: { children: ReactNode }) => <span className="rounded-full bg-accent-soft px-3 py-1 text-sm">{children}</span>

/** The cards Claude writes from the voice profile: tone, phrases, what to avoid, the voice mix and image habits. */
function Digest({ digest }: { digest: InsightsDigestOut }) {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <div className="min-w-0 space-y-5">
        <Section title="Tone & voice">
          <ul className="space-y-1.5">
            {digest.tone.map((line) => (
              <li key={line} className="flex gap-2.5">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-accent" aria-hidden />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </Section>
        {digest.signature_phrases.length > 0 && (
          <Section title="Signature phrases" hint="Quoted from your own writing.">
            <div className="flex flex-wrap gap-2">
              {digest.signature_phrases.map((phrase) => (
                <Chip key={phrase}>{phrase}</Chip>
              ))}
            </div>
          </Section>
        )}
        {digest.steer_clear.length > 0 && (
          <Section title="Steer clear of">
            <ul className="space-y-1.5">
              {digest.steer_clear.map((line) => (
                <li key={line} className="flex gap-2">
                  <X className="mt-1 size-4 shrink-0 text-danger" aria-hidden />
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          </Section>
        )}
      </div>
      <div className="min-w-0 space-y-5">
        {digest.voice_mix.length > 0 && (
          <Section title="Voice mix" aside={`${digest.sentences_labeled} sampled sentences`}>
            <WaffleChart slices={digest.voice_mix} />
            <p className="text-xs text-muted">Each square = 2% of the sentences sampled from your writing.</p>
            {digest.headline && <p className="font-semibold text-primary">{digest.headline}</p>}
          </Section>
        )}
        {(digest.image_habits.length > 0 || digest.caption_example) && (
          <Section title="Images & captions">
            <ul className="space-y-1.5">
              {digest.image_habits.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            {digest.caption_example && <p className="rounded-lg bg-sunken px-3 py-2 font-mono text-xs break-words">{digest.caption_example}</p>}
          </Section>
        )}
      </div>
    </div>
  )
}

function lessonText(lesson: LessonItem) {
  if (lesson.kind === 'remove') return <>You cut &ldquo;{lesson.old}&rdquo;</>
  if (lesson.kind === 'replace')
    return (
      <>
        &ldquo;{lesson.old}&rdquo; → &ldquo;{lesson.new}&rdquo;
      </>
    )
  return <>You asked: &ldquo;{lesson.old}&rdquo;</>
}

function TrackRecord({ track }: { track: TrackRecordOut }) {
  if (track.posts === 0)
    return (
      <Section title="Track record" className="lg:col-span-2">
        <p className="text-sm text-muted">
          No posts yet.{' '}
          <Link to="/projects/new" className="font-semibold text-accent hover:underline">
            Write your first post
          </Link>{' '}
          to see how closely it matches your voice.
        </p>
      </Section>
    )
  const scored = track.points.filter((p) => p.voice_match !== null || p.authenticity !== null)
  return (
    <Section title="Track record" hint="What this persona has written so far." className="lg:col-span-2">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatTile label="Posts" value={track.posts.toLocaleString()} />
        <StatTile label="Published" value={track.published.toLocaleString()} />
        <StatTile label="Words written" value={track.words.toLocaleString()} />
        <StatTile label="Images drawn" value={track.images.toLocaleString()} />
        <StatTile label="References" value={track.references.toLocaleString()} />
        <StatTile label="Playbook moves" value={track.playbook.toLocaleString()} />
      </div>
      {scored.length > 1 && <ScoreTrend points={track.points} />}
      {scored.length === 1 && (
        <p className="text-sm">
          <Link to={`/projects/${scored[0].project_id}`} className="font-semibold hover:text-accent">
            {scored[0].title}
          </Link>{' '}
          scored <span className="font-bold tabular-nums">{score(scored[0].voice_match)}</span> for voice match and{' '}
          <span className="font-bold tabular-nums">{score(scored[0].authenticity)}</span> for reading as human, out of 100.{' '}
          <span className="text-muted">The trend appears after your second post.</span>
        </p>
      )}
      <div className="grid gap-5 pt-1 lg:grid-cols-2">
        {(track.outcomes.length > 0 || track.meme_formats.length > 0) && (
          <div className="space-y-3">
            {track.outcomes.length > 0 && (
              <div>
                <h4 className="mb-1.5 text-sm font-semibold">How published posts did</h4>
                <div className="flex flex-wrap gap-2">
                  {track.outcomes.map((item) => {
                    const info = outcomeInfo(item.id)
                    return (
                      <Badge key={item.id} tone={info?.tone ?? 'neutral'}>
                        {info?.label ?? item.label} · {item.count}
                      </Badge>
                    )
                  })}
                </div>
              </div>
            )}
            {track.meme_formats.length > 0 && (
              <div>
                <h4 className="mb-1.5 text-sm font-semibold">Favorite closing memes</h4>
                <div className="flex flex-wrap gap-2">
                  {track.meme_formats.map((item) => (
                    <Chip key={item.id}>
                      {item.label}
                      <span className="text-muted"> · {item.count}</span>
                    </Chip>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        {track.lessons.length > 0 && (
          <div>
            <h4 className="mb-1.5 text-sm font-semibold">What you keep fixing</h4>
            <ul className="space-y-1 text-sm">
              {track.lessons.map((lesson) => (
                <li key={`${lesson.kind}-${lesson.old}-${lesson.new}`} className="break-words">
                  {lessonText(lesson)}
                  {lesson.count > 1 && <span className="text-muted"> · {lesson.count} times</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Section>
  )
}

/** Everything measured from samples and posts; needs no voice profile. */
function Measured({ data }: { data: PersonaInsightsOut }) {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      {data.fingerprint && data.fingerprint.rows.length > 0 && (
        <Section title="Style fingerprint" hint="How your writing measures up, from your own samples.">
          <DumbbellChart fingerprint={data.fingerprint} />
        </Section>
      )}
      {(data.openers.length > 0 || data.phrases.length > 0) && (
        <Section title="How you open and what you repeat">
          {data.openers.length > 0 && (
            <div>
              <h4 className="mb-2 text-sm font-semibold">Your first sentence is usually</h4>
              <BarList items={data.openers} unit={(n) => plural(n, 'post')} />
            </div>
          )}
          {data.phrases.length > 0 && (
            <div className="pt-2">
              <h4 className="mb-2 text-sm font-semibold">Phrases you come back to</h4>
              <div className="flex flex-wrap gap-2">
                {data.phrases.map((phrase) => (
                  <span key={phrase.id} title={`In ${plural(phrase.count, 'post')}`}>
                    <Chip>
                      {phrase.label}
                      {phrase.count > 1 && <span className="text-muted"> · {phrase.count}</span>}
                    </Chip>
                  </span>
                ))}
              </div>
              <p className="mt-2 text-xs text-muted">A number is how many of your posts use the phrase.</p>
            </div>
          )}
        </Section>
      )}
      <Section
        title="Formula flow"
        hint="How your posts are built: article type, opener, body and closer. A wider band means more posts."
        aside={data.formula.posts > 0 ? plural(data.formula.posts, 'post') : undefined}
        className="lg:col-span-2"
      >
        {data.formula.posts === 0 ? (
          <p className="text-sm text-muted">No posts yet. Each post you write adds a path here.</p>
        ) : (
          <SankeyChart flow={data.formula} />
        )}
      </Section>
      <TrackRecord track={data.track_record} />
    </div>
  )
}

/** The persona's Insights tab: a short digest of the voice plus charts about the writing and the posts. */
export function InsightsTab({ personaId, onOpenTab }: { personaId: number; onOpenTab: OpenTab }) {
  const qc = useQueryClient()
  const { data, isLoading, error } = usePersonaInsights(personaId)
  const refresh = useRefreshInsights(personaId)
  const [jobId, setJobId] = useState<string | null>(null)
  const job = useJob(jobId, () => {
    void qc.invalidateQueries({ queryKey: keys.insights(personaId) })
  })
  const running = refresh.isPending || (!!jobId && job.status !== 'succeeded' && job.status !== 'failed')

  if (isLoading) return <Spinner />
  if (error || !data) return <Notice tone="error">{error ? errorText(error) : 'Could not load the insights.'}</Notice>

  const { overview, digest } = data
  if (overview.own_samples === 0 && data.track_record.posts === 0)
    return (
      <EmptyState
        icon={<BarChart3 className="size-8" />}
        title="Nothing to chart yet"
        action={<Button onClick={() => onOpenTab('samples')}>Add writing samples</Button>}
      >
        Add a few of your own posts and Insights will show how you write: your tone, your voice mix, your habits.
      </EmptyState>
    )

  const hasProfile = overview.voice_profile_version !== null
  const start = () => refresh.mutate(undefined, { onSuccess: (started) => setJobId(started.id) })
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold">Insights</h2>
          <p className="text-sm text-muted">
            Built from {plural(overview.own_samples, 'writing sample')} · {overview.own_words.toLocaleString()} words
            {overview.updated_at && ` · updated ${new Date(overview.updated_at).toLocaleDateString()}`}
          </p>
        </div>
        {hasProfile && digest && (
          <Button variant="secondary" icon={<RefreshCw className="size-4" />} loading={running} onClick={start}>
            Refresh insights
          </Button>
        )}
      </div>

      {(refresh.error || job.status === 'failed') && (
        <Notice tone="error" title="Could not build the insights">
          {refresh.error ? errorText(refresh.error) : job.error}
        </Notice>
      )}
      {digest?.stale && (
        <Notice tone="warn">
          This summary describes voice profile v{digest.version}; you now use v{overview.voice_profile_version}. Refresh insights to bring it up to date.
        </Notice>
      )}
      {!digest && (
        <Notice title={hasProfile ? 'No summary for this voice profile yet' : 'Your tone, phrases and voice mix appear here'}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span>
              {hasProfile
                ? 'Claude can read your voice profile and sum it up in one short call.'
                : 'Generate your voice profile and Insights sums it up. The charts below are measured from your samples already.'}
            </span>
            {hasProfile ? (
              <Button size="sm" loading={running} onClick={start}>
                Build insights
              </Button>
            ) : (
              <Button size="sm" onClick={() => onOpenTab('voice')}>
                Go to voice profile
              </Button>
            )}
          </div>
        </Notice>
      )}

      {digest && <Digest digest={digest} />}
      <Measured data={data} />
    </div>
  )
}
