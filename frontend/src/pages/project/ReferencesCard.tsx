import { BookOpen, Dices, History, LocateFixed, MessageSquare, Newspaper, Plus, Quote, Trash2, Wrench, type LucideIcon } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import type { ProjectOut, ReferenceOut } from '../../api/types.gen'
import { Badge, Button, Card, Dialog, Notice, Select, Spinner } from '../../components/ui'
import { cx } from '../../lib/cx'
import { domain, kindLabel, kindsFor, type ReferenceKind } from '../../lib/references'
import type { ReferenceActions } from './useReferenceActions'

const KIND_ICON: Record<string, LucideIcon> = {
  source: BookOpen,
  quote: Quote,
  social_post: MessageSquare,
  resource: Wrench,
  related_article: Newspaper,
}

function KindIcon({ kind, className }: { kind: string; className?: string }) {
  const Icon = KIND_ICON[kind] ?? BookOpen
  return <Icon className={className ?? 'size-3.5'} aria-hidden />
}

function KindSwitcher({ reference, actions }: { reference: ReferenceOut; actions: ReferenceActions }) {
  const options = kindsFor(reference).filter((k) => k !== reference.kind)
  if (!options.length) return null
  return (
    <Select
      aria-label={`Switch ${kindLabel(reference.kind).toLowerCase()} to another kind`}
      title="Find a different kind of reference for the same spot"
      className="h-8 w-36 text-sm"
      value=""
      disabled={actions.disabled}
      onChange={(e) => e.target.value && actions.redraw(reference, e.target.value as ReferenceKind)}
    >
      <option value="">Switch to…</option>
      {options.map((kind) => (
        <option key={kind} value={kind}>
          {kindLabel(kind)}
        </option>
      ))}
    </Select>
  )
}

function showInPost(id: number) {
  const chip = document.querySelector<HTMLElement>(`[data-reference-id="${id}"]`)
  chip?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  chip?.focus({ preventScroll: true })
}

function ReferenceItem({ reference, actions }: { reference: ReferenceOut; actions: ReferenceActions }) {
  const [versionsOpen, setVersionsOpen] = useState(false)
  const redrawing = actions.redrawingId === reference.id
  const label = kindLabel(reference.kind)
  return (
    <li className="space-y-2 rounded-lg border border-line p-3" aria-label={`${label}: ${reference.title || 'not found yet'}`}>
      <div className="flex flex-wrap items-center gap-1.5 text-xs font-semibold text-muted">
        <KindIcon kind={reference.kind} />
        {label}
        {reference.placement === 'go_deeper' && <span>· Go deeper list</span>}
        {reference.status === 'ready' && !reference.in_post && <Badge>Edited out</Badge>}
      </div>
      {reference.status === 'ready' && (
        <div className="min-w-0">
          <a href={reference.url} target="_blank" rel="noreferrer" className="text-sm font-semibold break-words hover:underline">
            {reference.title || domain(reference.url)}
          </a>
          <p className="text-xs text-muted">{domain(reference.url)}</p>
          {reference.quote && (
            <p className="mt-1 line-clamp-3 text-xs text-muted italic">
              “{reference.quote}”{reference.speaker && ` — ${reference.speaker}`}
            </p>
          )}
        </div>
      )}
      {reference.status === 'error' && <Notice tone="error">{reference.error ?? 'This reference could not be found.'}</Notice>}
      {reference.status === 'pending' && <Spinner label="Searching…" />}
      {redrawing && <Spinner label={`Finding a new ${label.toLowerCase()}…`} />}
      <div className="flex flex-wrap gap-1.5">
        <Button
          size="sm"
          variant="secondary"
          icon={<Dices className="size-4" />}
          onClick={() => actions.redraw(reference)}
          disabled={actions.disabled}
          title={`Find a different ${label.toLowerCase()} for this spot`}
        >
          Redraw
        </Button>
        <KindSwitcher reference={reference} actions={actions} />
        {reference.in_post && (
          <Button size="sm" variant="ghost" icon={<LocateFixed className="size-4" />} onClick={() => showInPost(reference.id)} title="Show in post">
            <span className="sr-only">Show in post</span>
          </Button>
        )}
        {reference.history.length > 1 && (
          <Button
            size="sm"
            variant="ghost"
            icon={<History className="size-4" />}
            onClick={() => setVersionsOpen(true)}
            disabled={actions.disabled}
            aria-label={`${reference.history.length} versions`}
            title="Earlier versions of this reference"
          >
            {reference.history.length}
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          icon={<Trash2 className="size-4" />}
          onClick={() => actions.remove(reference)}
          disabled={actions.disabled}
          title="Take it out; the sentence reads as it did before"
        >
          <span className="sr-only">Remove {label.toLowerCase()}</span>
        </Button>
      </div>
      <Dialog open={versionsOpen} onClose={() => setVersionsOpen(false)} title={`${label} versions`}>
        <ul className="space-y-2">
          {reference.history.map((entry) => (
            <li key={entry.index}>
              <button
                type="button"
                className={cx('w-full rounded-lg border border-line p-3 text-left hover:border-accent', entry.url === reference.url && 'bg-accent-soft')}
                onClick={() => {
                  actions.revert(reference, entry.index)
                  setVersionsOpen(false)
                }}
              >
                <span className="block text-sm font-semibold">{entry.title || domain(entry.url)}</span>
                <span className="block text-xs text-muted">
                  v{entry.index + 1} · {kindLabel(entry.kind)} · {domain(entry.url)}
                  {entry.url === reference.url && ' · current'}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </Dialog>
    </li>
  )
}

/** The post's references: what each one is, where it links, and Redraw / switch kind / versions / remove. */
export function ReferencesCard({ project, actions }: { project: ProjectOut; actions: ReferenceActions }) {
  const refs = project.references
  const placed = refs.filter((r) => r.status === 'ready' && r.in_post).length
  return (
    <Card className="space-y-3">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="font-bold">References</h2>
        {refs.length > 0 && (
          <span className="text-xs text-muted">
            {placed} of {refs.length} in the post
          </span>
        )}
      </div>
      <p className="text-xs text-muted">
        Sources, quotes, posts and resources found on the web and worked into your post. Every link and quote comes from the search. Redraw any you don’t like.
      </p>
      {refs.length > 0 && (
        <ul className="space-y-2">
          {refs.map((ref) => (
            <ReferenceItem key={ref.id} reference={ref} actions={actions} />
          ))}
        </ul>
      )}
      {actions.enriching && <Spinner label="Finding references…" />}
      {actions.error && <Notice tone="error">{actions.error}</Notice>}
      <Button
        size="sm"
        variant="secondary"
        icon={<Plus className="size-4" />}
        onClick={() => actions.enrich(refs.length ? 1 : undefined)}
        disabled={actions.disabled}
      >
        {refs.length ? 'Add another' : 'Find references'}
      </Button>
    </Card>
  )
}

/** A link in the preview that belongs to a reference: the link, plus a small chip with its actions. */
export function ReferenceLink({ reference, actions, children }: { reference: ReferenceOut; actions: ReferenceActions; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const label = kindLabel(reference.kind)
  return (
    <span
      className="relative inline"
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOpen(false)
      }}
      onKeyDown={(e) => e.key === 'Escape' && setOpen(false)}
    >
      <a href={reference.url} target="_blank" rel="noreferrer">
        {children}
      </a>
      <button
        type="button"
        data-reference-id={reference.id}
        aria-label={`${label}: ${reference.title}. Show actions`}
        aria-expanded={open}
        title={`${label} · click to redraw or remove`}
        onClick={() => setOpen((v) => !v)}
        className={cx(
          'ml-0.5 inline-flex size-5 translate-y-[-1px] items-center justify-center rounded-full border border-line bg-accent-soft align-middle text-accent hover:border-accent',
          actions.redrawingId === reference.id && 'animate-pulse',
        )}
      >
        <KindIcon kind={reference.kind} className="size-3" />
      </button>
      {open && (
        <span
          role="menu"
          className="absolute top-full left-0 z-20 mt-1 block w-64 space-y-2 rounded-xl border border-line bg-surface p-3 font-sans text-sm not-italic shadow-lg"
        >
          <span className="block text-xs font-semibold text-muted">
            {label} · {domain(reference.url)}
          </span>
          <span className="block font-semibold">{reference.title}</span>
          <span className="flex flex-wrap gap-1.5">
            <Button
              size="sm"
              variant="secondary"
              icon={<Dices className="size-4" />}
              disabled={actions.disabled}
              onClick={() => {
                actions.redraw(reference)
                setOpen(false)
              }}
            >
              Redraw
            </Button>
            <KindSwitcher reference={reference} actions={actions} />
            <Button
              size="sm"
              variant="ghost"
              icon={<Trash2 className="size-4" />}
              disabled={actions.disabled}
              onClick={() => {
                actions.remove(reference)
                setOpen(false)
              }}
            >
              Remove
            </Button>
          </span>
        </span>
      )}
    </span>
  )
}
