import { useQuery } from '@tanstack/react-query'
import { BookUser, Dices, MessageCircleQuestion, Palette, Plus, Shuffle, Telescope, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { errorText } from '../api/client'
import { fetchSurprise, useArchetypes, usePersonaMutations, useVoiceInterview } from '../api/hooks'
import type { ArchetypeOut, PersonaOut, VoiceSourceIn } from '../api/types.gen'
import { cx } from '../lib/cx'
import { sourceSummary } from '../lib/onboarding'
import { Button, Card, Field, Input, Notice, Spinner, Textarea } from './ui'

type Path = 'archetype' | 'surprise' | 'blend' | 'interview'

const PATHS: { id: Path; title: string; promise: string; icon: ReactNode }[] = [
  { id: 'archetype', title: 'Pick a voice', promise: 'Choose from a library of ready-made writing voices.', icon: <Palette className="size-5" /> },
  {
    id: 'blend',
    title: 'Inspired by writers',
    promise: 'Name writers you admire; we study their public work for style.',
    icon: <Telescope className="size-5" />,
  },
  {
    id: 'interview',
    title: 'Answer a few questions',
    promise: 'Describe how you think and talk; we turn it into a voice.',
    icon: <MessageCircleQuestion className="size-5" />,
  },
  { id: 'surprise', title: 'Surprise me', promise: 'A random voice to get going. Shuffle until one fits.', icon: <Dices className="size-5" /> },
]

function DialSummary({ dials }: { dials: Record<string, number> }) {
  return (
    <p className="text-xs text-muted">
      Humor {dials.humor} · Storytelling {dials.storytelling} · Opinion {dials.opinion} · Technical depth {dials.technical_depth}
    </p>
  )
}

function VoiceCard({ a, selected, onSelect }: { a: ArchetypeOut; selected: boolean; onSelect?: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={onSelect ? selected : undefined}
      disabled={!onSelect}
      className={cx(
        'w-full rounded-xl border p-4 text-left transition',
        selected ? 'border-accent bg-accent-soft' : 'border-line bg-surface hover:border-accent/60',
      )}
    >
      <p className="font-bold">{a.name}</p>
      <p className="text-sm text-muted">{a.tagline}</p>
      <p className="mt-2 border-l-2 border-accent/60 pl-3 text-sm italic">{a.preview}</p>
      <div className="mt-2">
        <DialSummary dials={a.dials} />
      </div>
    </button>
  )
}

function ArchetypePicker({ onSave, busy }: { onSave: (body: VoiceSourceIn) => void; busy: boolean }) {
  const { data, isLoading } = useArchetypes()
  const [id, setId] = useState('')
  const [note, setNote] = useState('')
  if (isLoading) return <Spinner />
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        {data?.map((a) => (
          <VoiceCard key={a.id} a={a} selected={id === a.id} onSelect={() => setId(a.id)} />
        ))}
      </div>
      <Field label="Anything to add? (optional)" hint="e.g. “More playful, and I always explain with cooking metaphors.”" htmlFor="archetype-note">
        <Textarea id="archetype-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} />
      </Field>
      <Button disabled={!id} loading={busy} onClick={() => onSave({ source: 'archetype', spec: { archetype: id, note } })}>
        Use this voice
      </Button>
    </div>
  )
}

function SurpriseMe({ onSave, busy }: { onSave: (body: VoiceSourceIn) => void; busy: boolean }) {
  const [seed, setSeed] = useState(() => Math.floor(Math.random() * 1_000_000))
  const { data, isLoading, isFetching } = useQuery({ queryKey: ['voice-surprise', seed], queryFn: () => fetchSurprise(seed) })
  if (isLoading || !data) return <Spinner />
  return (
    <div className="space-y-4">
      <VoiceCard a={data.archetype} selected />
      {data.secondary && (
        <p className="text-sm text-muted">
          With a dash of <strong className="text-fg">{data.secondary.name}</strong>: {data.secondary.tagline}
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <Button variant="secondary" icon={<Shuffle className="size-4" />} loading={isFetching} onClick={() => setSeed(Math.floor(Math.random() * 1_000_000))}>
          Shuffle
        </Button>
        <Button loading={busy} onClick={() => onSave({ source: 'random', spec: data.spec })}>
          Use this voice
        </Button>
      </div>
    </div>
  )
}

function BlendBuilder({ onSave, busy }: { onSave: (body: VoiceSourceIn) => void; busy: boolean }) {
  const [writers, setWriters] = useState([{ name: '', weight: 7 }])
  const [topics, setTopics] = useState('')
  const named = writers.filter((w) => w.name.trim())
  const update = (i: number, patch: Partial<{ name: string; weight: number }>) => setWriters((ws) => ws.map((w, j) => (j === i ? { ...w, ...patch } : w)))
  return (
    <div className="space-y-4">
      <Notice title="Inspired by, never copied">
        We search for each writer's public work and note how they write: rhythm, structure, humor, point of view. Your posts become a fresh voice shaped by
        those habits, not an imitation, and nothing is reproduced. This works best for writers with a public blog or newsletter.
      </Notice>
      <div className="space-y-3">
        {writers.map((w, i) => (
          <div key={i} className="flex flex-wrap items-end gap-3">
            <div className="min-w-48 flex-1">
              <Field label={`Writer ${i + 1}`} htmlFor={`writer-${i}`}>
                <Input
                  id={`writer-${i}`}
                  value={w.name}
                  maxLength={80}
                  placeholder="A writer, blog or newsletter"
                  onChange={(e) => update(i, { name: e.target.value })}
                />
              </Field>
            </div>
            <div className="w-40">
              <Field label={`How much: ${w.weight}/10`} htmlFor={`weight-${i}`}>
                <input
                  id={`weight-${i}`}
                  type="range"
                  min={1}
                  max={10}
                  value={w.weight}
                  className="w-full accent-[var(--app-accent)]"
                  onChange={(e) => update(i, { weight: Number(e.target.value) })}
                />
              </Field>
            </div>
            {writers.length > 1 && (
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Remove writer ${i + 1}`}
                icon={<X className="size-4" />}
                onClick={() => setWriters((ws) => ws.filter((_, j) => j !== i))}
              />
            )}
          </div>
        ))}
        {writers.length < 4 && (
          <Button variant="secondary" size="sm" icon={<Plus className="size-4" />} onClick={() => setWriters((ws) => [...ws, { name: '', weight: 5 }])}>
            Add another writer
          </Button>
        )}
      </div>
      <Field label="What will you write about? (optional)" htmlFor="blend-topics">
        <Input
          id="blend-topics"
          value={topics}
          maxLength={300}
          placeholder="e.g. causal inference and leading data teams"
          onChange={(e) => setTopics(e.target.value)}
        />
      </Field>
      <Button disabled={!named.length} loading={busy} onClick={() => onSave({ source: 'blend', spec: { writers: named, topics } })}>
        Use these writers
      </Button>
      <p className="text-xs text-muted">The research runs when you generate your voice profile and needs a Claude connection.</p>
    </div>
  )
}

function InterviewFlow({ onSave, busy }: { onSave: (body: VoiceSourceIn) => void; busy: boolean }) {
  const { data, isLoading } = useVoiceInterview()
  const [answers, setAnswers] = useState<Record<string, string>>({})
  if (isLoading) return <Spinner />
  const filled = Object.values(answers).filter((a) => a.trim()).length
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted">Answer what you like and skip the rest. Write the way you talk: your wording is the best clue to your voice.</p>
      {data?.map((q, i) => (
        <Field key={q.id} label={`${i + 1}. ${q.question}`} hint={q.hint} htmlFor={`q-${q.id}`}>
          <Textarea
            id={`q-${q.id}`}
            rows={3}
            value={answers[q.id] ?? ''}
            maxLength={2000}
            onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
          />
        </Field>
      ))}
      <Button
        disabled={!filled}
        loading={busy}
        onClick={() => onSave({ source: 'interview', spec: { answers: Object.entries(answers).map(([id, answer]) => ({ id, answer })) } })}
      >
        Use my answers
      </Button>
    </div>
  )
}

/**
 * "I'm starting fresh": pick a way to get a voice without any writing of your own.
 * Saves the choice on the persona; generating the voice profile is the next step.
 */
export function VoiceStart({ persona, onChosen }: { persona: PersonaOut; onChosen?: () => void }) {
  const { setVoiceSource, clearVoiceSource } = usePersonaMutations()
  const archetypes = useArchetypes()
  const [path, setPath] = useState<Path | null>(null)
  const summary = sourceSummary(persona, archetypes.data)
  const save = (body: VoiceSourceIn) =>
    setVoiceSource.mutate(
      { id: persona.id, body },
      {
        onSuccess: () => {
          setPath(null)
          onChosen?.()
        },
      },
    )
  const busy = setVoiceSource.isPending
  return (
    <div className="space-y-4">
      {summary && (
        <Notice tone="success" title={summary}>
          <p>Next, generate your voice profile. You can change this choice or add your own posts at any time; the voice sharpens as you do.</p>
          <Button className="mt-2" size="sm" variant="ghost" loading={clearVoiceSource.isPending} onClick={() => clearVoiceSource.mutate(persona.id)}>
            Remove this starting voice
          </Button>
        </Notice>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        {PATHS.map((p) => (
          <button
            key={p.id}
            type="button"
            aria-pressed={path === p.id}
            onClick={() => setPath(path === p.id ? null : p.id)}
            className={cx(
              'flex items-start gap-3 rounded-xl border p-4 text-left transition',
              path === p.id ? 'border-accent bg-accent-soft' : 'border-line bg-surface hover:border-accent/60',
            )}
          >
            <span className="mt-0.5 text-accent" aria-hidden>
              {p.icon}
            </span>
            <span>
              <span className="block font-bold">{p.title}</span>
              <span className="block text-sm text-muted">{p.promise}</span>
            </span>
          </button>
        ))}
      </div>
      {setVoiceSource.error && <Notice tone="error">{errorText(setVoiceSource.error)}</Notice>}
      {path && (
        <Card className="space-y-2">
          {path === 'archetype' && <ArchetypePicker onSave={save} busy={busy} />}
          {path === 'surprise' && <SurpriseMe onSave={save} busy={busy} />}
          {path === 'blend' && <BlendBuilder onSave={save} busy={busy} />}
          {path === 'interview' && <InterviewFlow onSave={save} busy={busy} />}
        </Card>
      )}
    </div>
  )
}

/** The two-way fork at the top of the "Your voice" step. */
export function VoiceFork({ value, onChange }: { value: 'writing' | 'fresh'; onChange: (v: 'writing' | 'fresh') => void }) {
  const options = [
    {
      id: 'writing' as const,
      title: 'I have writing to share',
      text: 'Upload posts, import a URL or paste text. Your own words make the most accurate voice.',
    },
    { id: 'fresh' as const, title: "I'm starting fresh", text: 'No posts yet? Start from a ready-made voice, writers you admire, or a short interview.' },
  ]
  return (
    <div role="radiogroup" aria-label="Do you have writing samples?" className="grid gap-3 sm:grid-cols-2">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          role="radio"
          aria-checked={value === o.id}
          onClick={() => onChange(o.id)}
          className={cx(
            'flex items-start gap-3 rounded-xl border p-4 text-left transition',
            value === o.id ? 'border-accent bg-accent-soft' : 'border-line bg-surface hover:border-accent/60',
          )}
        >
          <BookUser className="mt-0.5 size-5 shrink-0 text-accent" aria-hidden />
          <span>
            <span className="block font-bold">{o.title}</span>
            <span className="block text-sm text-muted">{o.text}</span>
          </span>
        </button>
      ))}
    </div>
  )
}
