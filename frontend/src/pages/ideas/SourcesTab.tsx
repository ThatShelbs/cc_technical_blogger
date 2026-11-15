import { CheckCircle2, CircleAlert, Plus, RotateCcw, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { errorText } from '../../api/client'
import { useIdeaLabMutations, useIdeaSources } from '../../api/hooks'
import type { IdeaSourceOut, IdeaSourcesOut } from '../../api/types.gen'
import { Button, Card, Field, Input, Notice, Spinner, Switch, Textarea } from '../../components/ui'
import { parseNames } from '../../lib/ideas'

function Health({ source }: { source: IdeaSourceOut }) {
  if (source.ok === null || source.ok === undefined) return <span className="text-xs text-muted">Not read yet</span>
  if (source.ok)
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted">
        <CheckCircle2 className="size-3.5 text-success" aria-hidden />
        {source.count} {source.count === 1 ? 'item' : 'items'} at the last refresh
      </span>
    )
  return (
    <span className="inline-flex items-center gap-1 text-xs text-danger">
      <CircleAlert className="size-3.5" aria-hidden />
      {source.error || 'Did not answer'}
    </span>
  )
}

/** A list of names edited as text, saved on demand. Remounted (by `key`) when the saved list changes. */
function NamesCard({
  title,
  hint,
  label,
  names,
  saving,
  onSave,
}: {
  title: string
  hint: string
  label: string
  names: string[]
  saving: boolean
  onSave: (names: string[]) => void
}) {
  const [text, setText] = useState(names.join('\n'))
  const parsed = parseNames(text)
  const changed = parsed.join('\n') !== names.join('\n')
  const id = `idea-names-${label}`
  return (
    <Card className="space-y-3">
      <div>
        <h3 className="text-lg font-bold">{title}</h3>
        <p className="text-sm text-muted">{hint}</p>
      </div>
      <Field label={label} htmlFor={id} hint="One per line.">
        <Textarea id={id} rows={Math.min(14, Math.max(5, names.length + 1))} value={text} onChange={(e) => setText(e.target.value)} />
      </Field>
      <Button size="sm" disabled={!changed} loading={saving} onClick={() => onSave(parsed)}>
        Save
      </Button>
    </Card>
  )
}

export function SourcesTab() {
  const { data, isLoading } = useIdeaSources()
  const { saveSources } = useIdeaLabMutations()
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  if (isLoading || !data) return <Spinner />

  const disabled = data.sources.filter((s) => !s.enabled).map((s) => s.id)
  const custom = data.sources.filter((s) => !s.builtin).map((s) => ({ name: s.name, url: s.url }))
  const groups = new Map<string, IdeaSourceOut[]>()
  for (const source of data.sources) groups.set(source.group_label, [...(groups.get(source.group_label) ?? []), source])
  const toggle = (source: IdeaSourceOut, on: boolean) =>
    saveSources.mutate({ disabled: on ? disabled.filter((id) => id !== source.id) : [...disabled, source.id] })
  const key = (config: IdeaSourcesOut, field: 'voices' | 'industries') => config[field].join('|')

  return (
    <div className="space-y-6">
      <Notice>
        Feeds are read directly: free, no keys, and nothing about you is sent. Places with no open feed are covered by Claude&rsquo;s web search during a
        refresh: {data.search_only.join('; ')}.
      </Notice>
      {saveSources.error && <Notice tone="error">{errorText(saveSources.error)}</Notice>}

      <div className="grid gap-6 lg:grid-cols-2">
        <NamesCard
          key={`voices-${key(data, 'voices')}`}
          title="People to watch"
          hint="A scout looks for what these people are claiming and arguing about, then for anyone else whose post is spreading."
          label="Watchlist"
          names={data.voices}
          saving={saveSources.isPending}
          onSave={(voices) => saveSources.mutate({ voices })}
        />
        <NamesCard
          key={`industries-${key(data, 'industries')}`}
          title="Industries"
          hint="Each industry gets its own news feed and its own scout, looking for the project many organisations are building at once."
          label="Industries"
          names={data.industries}
          saving={saveSources.isPending}
          onSave={(industries) => saveSources.mutate({ industries })}
        />
      </div>

      <Card className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold">Feeds</h3>
            <p className="text-sm text-muted">Switch off what you do not care about. A feed that stops answering is shown here and never stops a refresh.</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            icon={<RotateCcw className="size-4" />}
            onClick={() => {
              if (confirm('Put every feed, the watchlist and the industries back as shipped? Feeds you added are removed.')) saveSources.mutate({ reset: true })
            }}
          >
            Reset to defaults
          </Button>
        </div>
        {[...groups.entries()].map(([label, sources]) => (
          <section key={label} aria-label={label}>
            <h4 className="mb-1 text-sm font-bold tracking-wide text-muted uppercase">{label}</h4>
            <ul className="divide-y divide-line">
              {sources.map((source) => (
                <li key={source.id} className="flex items-center gap-3 py-2">
                  <Switch checked={source.enabled} onChange={(on) => toggle(source, on)} label={`Read ${source.name}`} disabled={saveSources.isPending} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold">{source.name}</p>
                    <Health source={source} />
                  </div>
                  {!source.builtin && (
                    <button
                      type="button"
                      className="rounded-md p-1.5 text-muted hover:bg-danger-soft hover:text-danger"
                      aria-label={`Remove ${source.name}`}
                      onClick={() => saveSources.mutate({ custom: custom.filter((c) => c.url !== source.url) })}
                    >
                      <Trash2 className="size-4" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </section>
        ))}

        <form
          className="grid gap-3 border-t border-line pt-4 sm:grid-cols-[1fr_2fr_auto] sm:items-end"
          onSubmit={(e) => {
            e.preventDefault()
            saveSources.mutate(
              { custom: [...custom, { name: name.trim(), url: url.trim() }] },
              {
                onSuccess: () => {
                  setName('')
                  setUrl('')
                },
              },
            )
          }}
        >
          <Field label="Add a feed" htmlFor="idea-feed-name">
            <Input id="idea-feed-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" required maxLength={80} />
          </Field>
          <Field label="RSS or Atom address" htmlFor="idea-feed-url">
            <Input id="idea-feed-url" type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/feed" required />
          </Field>
          <Button type="submit" variant="secondary" icon={<Plus className="size-4" />} loading={saveSources.isPending}>
            Add
          </Button>
        </form>
        <p className="text-xs text-muted">Any blog, newsletter or publication with a feed works, including most Substack and Medium publications.</p>
      </Card>
    </div>
  )
}
