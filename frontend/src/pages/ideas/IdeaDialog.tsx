import { Bookmark, ExternalLink, Flame, FlaskConical, Pencil, SlidersHorizontal, X } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { errorText } from '../../api/client'
import { useIdeaLabMutations } from '../../api/hooks'
import type { IdeaOut, PersonaOut } from '../../api/types.gen'
import { Badge, Button, Dialog, Field, Input, Notice, Select, Textarea } from '../../components/ui'
import { SCORES, scoreOf, SHELF_LIFE } from '../../lib/ideas'
import { LifecycleLine, StageBadge } from './IdeaCard'

function ScoreBars({ idea }: { idea: IdeaOut }) {
  const note = typeof idea.scores?.note === 'string' ? idea.scores.note : ''
  return (
    <div className="space-y-2">
      <dl className="space-y-1.5">
        {SCORES.map(({ key, label, hint }) => {
          const value = scoreOf(idea, key)
          return (
            <div key={key} className="grid grid-cols-[8.5rem_1fr_1.5rem] items-center gap-2 text-sm" title={hint}>
              <dt className="text-muted">{label}</dt>
              <dd className="h-2 overflow-hidden rounded-full bg-surface-2">
                <div className="h-full rounded-full bg-accent" style={{ width: `${value * 10}%` }} />
              </dd>
              <span className="text-right font-semibold tabular-nums">{value}</span>
            </div>
          )
        })}
      </dl>
      {note && <p className="text-sm text-muted">{note}</p>}
    </div>
  )
}

/** Change the title, brief and outline before writing; saved to the idea so the brief the writer gets matches. */
function EditIdea({ idea, onDone }: { idea: IdeaOut; onDone: () => void }) {
  const { updateIdea } = useIdeaLabMutations()
  const [title, setTitle] = useState(idea.title)
  const [brief, setBrief] = useState(idea.brief)
  const [outline, setOutline] = useState(idea.outline.join('\n'))
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault()
        updateIdea.mutate({ id: idea.id, body: { title, brief, outline: outline.split('\n').filter((l) => l.trim()) } }, { onSuccess: onDone })
      }}
    >
      <Field label="Title" htmlFor="idea-title">
        <Input id="idea-title" value={title} onChange={(e) => setTitle(e.target.value)} required minLength={3} maxLength={200} />
      </Field>
      <Field label="Brief" htmlFor="idea-brief">
        <Textarea id="idea-brief" rows={3} value={brief} onChange={(e) => setBrief(e.target.value)} maxLength={2000} />
      </Field>
      <Field label="Outline" htmlFor="idea-outline" hint="One point per line.">
        <Textarea id="idea-outline" rows={7} value={outline} onChange={(e) => setOutline(e.target.value)} />
      </Field>
      {updateIdea.error && <Notice tone="error">{errorText(updateIdea.error)}</Notice>}
      <div className="flex gap-2">
        <Button type="submit" loading={updateIdea.isPending}>
          Save changes
        </Button>
        <Button variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

/** The author's own note on the idea; kept through every stage, even once it is a post. */
function NoteField({ idea }: { idea: IdeaOut }) {
  const { updateIdea } = useIdeaLabMutations()
  const [draft, setDraft] = useState<{ id: number; text: string } | null>(null)
  const text = draft?.id === idea.id ? draft.text : idea.note
  const changed = text.trim() !== idea.note
  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault()
        updateIdea.mutate({ id: idea.id, body: { note: text } }, { onSuccess: () => setDraft(null) })
      }}
    >
      <Field label="Your note" htmlFor="idea-note" hint="Only for you: what you would add, who to ask, what to check.">
        <Textarea id="idea-note" rows={2} maxLength={2000} value={text} onChange={(e) => setDraft({ id: idea.id, text: e.target.value })} />
      </Field>
      {changed && (
        <Button type="submit" size="sm" variant="secondary" loading={updateIdea.isPending}>
          Save note
        </Button>
      )}
    </form>
  )
}

export function IdeaDialog({ idea, personas, onClose }: { idea: IdeaOut | null; personas: PersonaOut[]; onClose: () => void }) {
  const navigate = useNavigate()
  const { writeIdea, updateIdea } = useIdeaLabMutations()
  const [personaId, setPersonaId] = useState<number | undefined>(undefined)
  // Editing is tied to one idea: opening another shows it read-only.
  const [editingId, setEditingId] = useState<number | null>(null)
  if (!idea)
    return (
      <Dialog open={false} onClose={onClose} title="Idea">
        {null}
      </Dialog>
    )

  const editing = editingId === idea.id
  const writers = personas.filter((p) => p.voice_profile_version)
  const chosen = writers.find((p) => p.id === (personaId ?? idea.persona_id)) ?? writers.find((p) => p.is_active) ?? writers[0]
  const used = idea.state === 'used'
  const own = idea.approach === 'own'
  const write = (mode: 'standard' | 'ab') =>
    writeIdea.mutate(
      { id: idea.id, body: { persona_id: chosen?.id, mode } },
      { onSuccess: (data) => navigate(`/projects/${data.project.id}${data.job_id ? `?job=${data.job_id}` : ''}`) },
    )
  const setState = (state: 'new' | 'saved' | 'dismissed') => updateIdea.mutate({ id: idea.id, body: { state } })

  return (
    <Dialog open onClose={onClose} title={editing ? 'Edit idea' : idea.title} wide>
      {editing ? (
        <EditIdea idea={idea} onDone={() => setEditingId(null)} />
      ) : (
        <div className="space-y-5">
          <LifecycleLine idea={idea} />
          <div className="flex flex-wrap items-center gap-1.5">
            {own ? null : <Badge tone="flame">#{idea.rank}</Badge>}
            <StageBadge idea={idea} />
            <Badge tone="accent">{idea.approach_label}</Badge>
            {idea.theme && <Badge>{idea.theme}</Badge>}
            {!own && <Badge>{SHELF_LIFE[idea.shelf_life] ?? idea.shelf_life}</Badge>}
            {idea.tags.map((tag) => (
              <Badge key={tag}>{tag}</Badge>
            ))}
            {!used && (
              <Button size="sm" variant="ghost" className="ml-auto" icon={<Pencil className="size-3.5" />} onClick={() => setEditingId(idea.id)}>
                Edit
              </Button>
            )}
          </div>

          <p>{idea.brief}</p>
          {idea.angle && (
            <p className="rounded-lg bg-accent-soft px-3 py-2 text-sm">
              <span className="font-semibold">Your angle: </span>
              {idea.angle}
            </p>
          )}
          {idea.builds_on && <p className="text-sm text-muted">Follows on from &ldquo;{idea.builds_on}&rdquo;.</p>}

          <div className="grid gap-5 md:grid-cols-[1fr_17rem]">
            <div className="space-y-4">
              <div>
                <h3 className="mb-1.5 font-bold">Outline</h3>
                <ol className="list-decimal space-y-1 pl-5">
                  {idea.outline.map((point) => (
                    <li key={point}>{point}</li>
                  ))}
                </ol>
              </div>
              {idea.why_now && (
                <div>
                  <h3 className="mb-1 font-bold">Why now</h3>
                  <p className="text-sm">{idea.why_now}</p>
                </div>
              )}
              {idea.evidence.length > 0 && (
                <div>
                  <h3 className="mb-1 font-bold">Where this comes from</h3>
                  <ul className="space-y-1 text-sm">
                    {idea.evidence.map((link) => (
                      <li key={link.url}>
                        <a href={link.url} target="_blank" rel="noreferrer noopener" className="inline-flex items-start gap-1.5 text-accent hover:underline">
                          <ExternalLink className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                          <span className="break-words">{link.title}</span>
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            <div className="space-y-4">
              {!own && (
                <div>
                  <h3 className="mb-1.5 font-bold">Why it ranks #{idea.rank}</h3>
                  <ScoreBars idea={idea} />
                </div>
              )}
              <NoteField idea={idea} />
            </div>
          </div>

          {used ? (
            <Notice tone="success">
              This idea is a post{idea.project_title ? <> : &ldquo;{idea.project_title}&rdquo;</> : null} ({idea.stage_label}).{' '}
              {idea.project_id && (
                <Link to={`/projects/${idea.project_id}`} className="font-semibold underline">
                  Open the post
                </Link>
              )}{' '}
              Mark the post Ready or Published, and rate how it did, on the post itself; this idea follows along.
            </Notice>
          ) : (
            <div className="space-y-3 border-t border-line pt-4">
              {writers.length === 0 ? (
                <Notice tone="warn">
                  No persona has a voice profile yet.{' '}
                  <Link to="/personas" className="font-semibold underline">
                    Generate one to write this.
                  </Link>
                </Notice>
              ) : (
                <Field label="Write it as" htmlFor="idea-writer">
                  <Select id="idea-writer" className="max-w-xs" value={chosen?.id ?? ''} onChange={(e) => setPersonaId(Number(e.target.value))}>
                    {writers.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </Select>
                </Field>
              )}
              {writeIdea.error && <Notice tone="error">{errorText(writeIdea.error)}</Notice>}
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="flame" icon={<Flame className="size-4" />} disabled={!chosen} loading={writeIdea.isPending} onClick={() => write('standard')}>
                  Write this post
                </Button>
                <Button variant="secondary" icon={<FlaskConical className="size-4" />} disabled={!chosen || writeIdea.isPending} onClick={() => write('ab')}>
                  A/B test it
                </Button>
                <Link to={`/projects/new?idea=${idea.id}`}>
                  <Button variant="secondary" icon={<SlidersHorizontal className="size-4" />}>
                    Customize first
                  </Button>
                </Link>
                <span className="ml-auto flex gap-1">
                  <Button variant="ghost" size="sm" icon={<Bookmark className="size-4" />} onClick={() => setState(idea.state === 'saved' ? 'new' : 'saved')}>
                    {idea.state === 'saved' ? 'Saved' : 'Save'}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={<X className="size-4" />}
                    onClick={() => {
                      setState(idea.state === 'dismissed' ? 'new' : 'dismissed')
                      onClose()
                    }}
                  >
                    {idea.state === 'dismissed' ? 'Bring back' : 'Dismiss'}
                  </Button>
                </span>
              </div>
              <p className="text-xs text-muted">An A/B test writes the post twice and costs about twice as much.</p>
            </div>
          )}
        </div>
      )}
    </Dialog>
  )
}
