import { ExternalLink, Flame, RefreshCw, Search, X } from 'lucide-react'
import { useState } from 'react'

import { errorText } from '../../api/client'
import { useIdeaLab, useIdeaLabMutations } from '../../api/hooks'
import type { IdeaTrendOut } from '../../api/types.gen'
import { useJob } from '../../api/useJob'
import { Badge, Button, Card, EmptyState, Input, Notice, ProgressBar, Select, Spinner, StatTile } from '../../components/ui'
import { ago, groupTrends } from '../../lib/ideas'

type Depth = 'quick' | 'standard' | 'deep'

function Trend({ trend, onRemove }: { trend: IdeaTrendOut; onRemove: () => void }) {
  return (
    <Card className="space-y-2">
      <div className="flex items-start gap-2">
        <h3 className="min-w-0 flex-1 font-bold">{trend.label}</h3>
        <span className="inline-flex shrink-0 items-center gap-1 text-sm font-semibold" title="How much attention it is getting, out of 10">
          <Flame className="size-4 text-accent" aria-hidden />
          <span className="sr-only">Heat </span>
          {trend.heat}/10
        </span>
        <button
          type="button"
          className="shrink-0 rounded-md p-1 text-muted hover:bg-danger-soft hover:text-danger"
          aria-label={`Remove ${trend.label}`}
          onClick={onRemove}
        >
          <X className="size-4" />
        </button>
      </div>
      <p className="text-sm">{trend.summary}</p>
      {trend.industries.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {trend.industries.map((industry) => (
            <Badge key={industry}>{industry}</Badge>
          ))}
        </div>
      )}
      <ul className="space-y-0.5 text-sm">
        {trend.evidence.map((link) => (
          <li key={link.url}>
            <a href={link.url} target="_blank" rel="noreferrer noopener" className="inline-flex items-start gap-1.5 text-accent hover:underline">
              <ExternalLink className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              <span className="break-words">{link.title}</span>
            </a>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted">Last seen {ago(trend.last_seen)}</p>
    </Card>
  )
}

export function ResearchTab({ openSources }: { openSources: () => void }) {
  const lab = useIdeaLab()
  const { research, deleteTrend, refreshLab } = useIdeaLabMutations()
  const [query, setQuery] = useState('')
  const [depth, setDepth] = useState<Depth>('standard')
  const [started, setStarted] = useState<string | null>(null)
  const jobId = started ?? lab.data?.active_job_id ?? null
  const job = useJob(jobId, () => {
    setStarted(null)
    refreshLab()
  })
  const running = !!jobId && job.status !== 'succeeded' && job.status !== 'failed'
  const start = (body: { query?: string; depth: Depth }) =>
    research.mutate(body, {
      onSuccess: (data) => {
        setStarted(data.id)
        setQuery('')
      },
    })

  if (lab.isLoading) return <Spinner />
  const data = lab.data
  const groups = groupTrends(data?.trends ?? [])

  return (
    <div className="space-y-6">
      <Card className="space-y-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatTile label="Trends on file" value={(data?.trends.length ?? 0).toLocaleString()} />
          <StatTile label="Items collected" value={(data?.signals ?? 0).toLocaleString()} hint="Feed entries and pages the searches cited" />
          <StatTile label="Last full refresh" value={data?.last_refresh ? ago(data.last_refresh) : 'Never'} />
          <StatTile label="Extra searches" value={(data?.searches.length ?? 0).toLocaleString()} />
        </div>

        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (query.trim().length >= 3) start({ query, depth })
          }}
        >
          <div className="min-w-64 flex-1 space-y-1.5">
            <label htmlFor="idea-search" className="block text-sm font-semibold">
              Send another search
            </label>
            <Input
              id="idea-search"
              value={query}
              maxLength={300}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="A product, a person, a debate, an industry: anything you want looked into"
            />
          </div>
          <Button type="submit" icon={<Search className="size-4" />} disabled={running || query.trim().length < 3} loading={research.isPending && !!query}>
            Search and add
          </Button>
        </form>
        <p className="text-sm text-muted">
          Each search is added to what is already on file, so you can keep going until the picture is complete. The next brainstorm uses all of it.
        </p>

        <div className="flex flex-wrap items-end gap-2 border-t border-line pt-4">
          <div className="space-y-1.5">
            <label htmlFor="idea-depth" className="block text-sm font-semibold">
              Full refresh
            </label>
            <Select id="idea-depth" className="w-auto" value={depth} onChange={(e) => setDepth(e.target.value as Depth)}>
              <option value="quick">Quick: fewer searches per scout</option>
              <option value="standard">Standard</option>
              <option value="deep">Deep: nearly twice the searches</option>
            </Select>
          </div>
          <Button variant="secondary" icon={<RefreshCw className="size-4" />} disabled={running} onClick={() => start({ depth })}>
            Refresh everything
          </Button>
          <button type="button" className="ml-auto text-sm font-semibold text-accent hover:underline" onClick={openSources}>
            Choose sources and people to watch
          </button>
        </div>
        <p className="text-sm text-muted">
          A full refresh reads every feed, then sends out web search scouts for launches, notable voices, what other writers are publishing, practitioner
          communities and each of your industries. It takes several minutes.
        </p>

        {research.error && <Notice tone="error">{errorText(research.error)}</Notice>}
        {running && (
          <div className="space-y-2">
            <p className="font-semibold">{job.message || 'Starting the research'}</p>
            <ProgressBar value={job.progress} label="Research progress" />
          </div>
        )}
        {job.status === 'failed' && <Notice tone="error">{job.error}</Notice>}
        {!!data?.scouts_failed.length && (
          <Notice tone="warn" title="Some scouts could not finish at the last refresh">
            {data.scouts_failed.join(', ')}. The rest of the research is still usable; refresh to try them again.
          </Notice>
        )}
      </Card>

      {!!data?.searches.length && (
        <div className="flex flex-wrap items-center gap-1.5 text-sm">
          <span className="text-muted">Your searches:</span>
          {data.searches.map((s) => (
            <Badge key={`${s.query}-${s.at}`}>
              {s.query} · {s.trends} {s.trends === 1 ? 'trend' : 'trends'}
            </Badge>
          ))}
        </div>
      )}

      {groups.length === 0 && !running && (
        <EmptyState icon={<Search className="size-8" />} title="No research yet">
          Refresh everything to see what is happening in AI, machine learning, data science and analytics right now, or send a search of your own.
        </EmptyState>
      )}
      {groups.map((group) => (
        <section key={group.id} aria-label={group.label} className="space-y-3">
          <h2 className="text-lg font-bold">
            {group.label} <span className="text-sm font-normal text-muted">({group.trends.length})</span>
          </h2>
          <div className="grid gap-4 lg:grid-cols-2">
            {group.trends.map((trend) => (
              <Trend key={trend.id} trend={trend} onRemove={() => deleteTrend.mutate(trend.id)} />
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}
