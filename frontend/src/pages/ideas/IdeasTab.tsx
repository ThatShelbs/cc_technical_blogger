import { useQueryClient } from '@tanstack/react-query'
import { ChevronDown, FileText, Lightbulb, Sparkles, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { errorText } from '../../api/client'
import { keys, useIdeaLab, useIdeaLabMutations, useIdeaSession, useIdeaSessions, usePersonas } from '../../api/hooks'
import type { IdeaSessionIn, PersonaOut } from '../../api/types.gen'
import { useJob } from '../../api/useJob'
import { Button, Card, EmptyState, Field, Notice, ProgressBar, Select, Spinner, Textarea } from '../../components/ui'
import { cx } from '../../lib/cx'
import { ago, FILTERS, filterIdeas, groupIdeas, MODES, parseDate, SORTS, type IdeaFilter, type IdeaMode, type IdeaSort } from '../../lib/ideas'
import { IdeaCard } from './IdeaCard'
import { IdeaDialog } from './IdeaDialog'

type ResearchChoice = 'auto' | 'refresh' | 'reuse'
const RESEARCH: Record<ResearchChoice, boolean | null> = { auto: null, refresh: true, reuse: false }

export function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: { id: T; label: string; count?: number }[]
  value: T
  onChange: (value: T) => void
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex flex-wrap rounded-lg border border-line bg-surface p-0.5">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          aria-pressed={value === option.id}
          onClick={() => onChange(option.id)}
          className={cx(
            'rounded-md px-3 py-1 text-sm font-semibold',
            value === option.id ? 'bg-accent-soft text-fg' : 'text-muted hover:bg-surface-2 hover:text-fg',
          )}
        >
          {option.label}
          {option.count !== undefined && ` (${option.count})`}
        </button>
      ))}
    </div>
  )
}

/** The form that starts a brainstorm: who it is for, how many ideas, and optional steering. */
function BrainstormCard({
  personas,
  busy,
  fresh,
  lastRefresh,
  onStart,
  error,
}: {
  personas: PersonaOut[]
  busy: boolean
  fresh: boolean
  lastRefresh: string | null
  onStart: (body: IdeaSessionIn) => void
  error: unknown
}) {
  const active = personas.find((p) => p.is_active) ?? personas[0]
  const [personaId, setPersonaId] = useState<number | undefined>(undefined)
  const [mode, setMode] = useState<IdeaMode>('light')
  const [more, setMore] = useState(false)
  const [focus, setFocus] = useState('')
  const [sparks, setSparks] = useState('')
  const [questions, setQuestions] = useState(true)
  const [counter, setCounter] = useState(true)
  const [research, setResearch] = useState<ResearchChoice>('auto')
  const chosen = personaId ?? active?.id
  const count = MODES.find((m) => m.id === mode)?.count ?? 10
  const willResearch = research === 'refresh' || (research === 'auto' && !fresh)

  return (
    <Card className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-[16rem_1fr]">
        <Field label="Ideas for" htmlFor="idea-persona" hint="Ideas fit this persona's portfolio and voice. You can still write one as another persona.">
          <Select id="idea-persona" value={chosen ?? ''} onChange={(e) => setPersonaId(Number(e.target.value))}>
            {personas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
        </Field>
        <div className="space-y-1.5">
          <p className="text-sm font-semibold" id="idea-mode-label">
            How many ideas
          </p>
          <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-labelledby="idea-mode-label">
            {MODES.map((option) => (
              <button
                key={option.id}
                type="button"
                role="radio"
                aria-checked={mode === option.id}
                onClick={() => setMode(option.id)}
                className={cx(
                  'rounded-xl border px-4 py-2.5 text-left',
                  mode === option.id ? 'border-accent bg-accent-soft' : 'border-line hover:bg-surface-2',
                )}
              >
                <span className="block font-semibold">
                  {option.label} · {option.count} ideas
                </span>
                <span className="block text-sm text-muted">{option.hint}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <button
        type="button"
        className="flex items-center gap-1.5 text-sm font-semibold text-muted hover:text-fg"
        aria-expanded={more}
        onClick={() => setMore((v) => !v)}
      >
        <ChevronDown className={cx('size-4 transition', more && 'rotate-180')} aria-hidden />
        Steer it
      </button>
      {more && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Field
            label="What do you want more of?"
            htmlFor="idea-focus"
            hint="Optional. For example: hands-on tutorials, or anything about agents in insurance."
          >
            <Textarea id="idea-focus" rows={3} maxLength={1000} value={focus} onChange={(e) => setFocus(e.target.value)} />
          </Field>
          <Field label="Your sparks" htmlFor="idea-sparks" hint="Optional. Paste links, notes or half-ideas; some of the ideas will develop them.">
            <Textarea id="idea-sparks" rows={3} maxLength={6000} value={sparks} onChange={(e) => setSparks(e.target.value)} />
          </Field>
          <fieldset className="space-y-2">
            <legend className="text-sm font-semibold">Also include</legend>
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-1 accent-[var(--app-accent)]" checked={questions} onChange={(e) => setQuestions(e.target.checked)} />
              <span>
                <span className="font-semibold">Reader Questions</span>
                <span className="block text-muted">Posts that answer what practitioners keep asking.</span>
              </span>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-1 accent-[var(--app-accent)]" checked={counter} onChange={(e) => setCounter(e.target.checked)} />
              <span>
                <span className="font-semibold">Counter-takes</span>
                <span className="block text-muted">Posts that push back on a claim that is spreading.</span>
              </span>
            </label>
          </fieldset>
          <Field
            label="Live research"
            htmlFor="idea-research"
            hint={lastRefresh ? `Last refreshed ${ago(lastRefresh)}.` : 'Not researched yet: the first brainstorm does it, which takes a few minutes.'}
          >
            <Select id="idea-research" value={research} onChange={(e) => setResearch(e.target.value as ResearchChoice)}>
              <option value="auto">Automatic: research again if it is more than a day old</option>
              <option value="refresh">Research first, then brainstorm</option>
              <option value="reuse">Use what is on file</option>
            </Select>
          </Field>
        </div>
      )}

      {error ? <Notice tone="error">{errorText(error)}</Notice> : null}
      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="flame"
          size="lg"
          icon={<Sparkles className="size-5" />}
          disabled={!chosen || busy}
          onClick={() =>
            onStart({
              persona_id: chosen,
              mode,
              focus,
              sparks,
              extras: [...(questions ? (['reader_questions'] as const) : []), ...(counter ? (['counter_take'] as const) : [])],
              refresh_research: RESEARCH[research],
            })
          }
        >
          Brainstorm {count} ideas
        </Button>
        <p className="text-sm text-muted">
          {willResearch
            ? 'Researches the web first, then writes and ranks the ideas. Expect several minutes.'
            : 'Uses the research on file, then writes and ranks the ideas.'}
        </p>
      </div>
    </Card>
  )
}

export function IdeasTab({ openResearch }: { openResearch: () => void }) {
  const qc = useQueryClient()
  const { data: personas, isLoading } = usePersonas()
  const lab = useIdeaLab()
  const sessions = useIdeaSessions()
  const { brainstorm, updateIdea, deleteSession, refreshLab, refreshSessions } = useIdeaLabMutations()
  const [picked, setPicked] = useState<number | null>(null)
  const [sort, setSort] = useState<IdeaSort>('best')
  const [filter, setFilter] = useState<IdeaFilter>('open')
  const [openId, setOpenId] = useState<number | null>(null)

  const sessionId = picked ?? sessions.data?.[0]?.id ?? null
  const session = useIdeaSession(sessionId)
  const running = session.data?.status === 'running' ? session.data.job_id : null
  const job = useJob(running, () => {
    void qc.invalidateQueries({ queryKey: keys.ideaSession(sessionId ?? 0) })
    void refreshSessions()
    refreshLab()
  })
  const busy = brainstorm.isPending || !!running

  if (isLoading) return <Spinner />
  if (!personas?.length)
    return (
      <EmptyState
        icon={<Lightbulb className="size-8" />}
        title="Create a persona first"
        action={
          <Link to="/welcome">
            <Button variant="flame">Set up my voice</Button>
          </Link>
        }
      >
        Ideas are built around a persona&rsquo;s portfolio and voice.
      </EmptyState>
    )

  const ideas = session.data?.items ?? []
  const shown = filterIdeas(ideas, filter)
  const groups = groupIdeas(shown, sort)
  const opened = ideas.find((i) => i.id === openId) ?? null

  return (
    <div className="space-y-6">
      <BrainstormCard
        personas={personas}
        busy={busy}
        fresh={!!lab.data?.fresh}
        lastRefresh={lab.data?.last_refresh ?? null}
        error={brainstorm.error}
        onStart={(body) => brainstorm.mutate(body, { onSuccess: (data) => setPicked(data.session.id) })}
      />

      {running && (
        <Card className="space-y-2">
          <p className="font-semibold">{job.message || 'Starting the brainstorm'}</p>
          <ProgressBar value={job.progress} label="Brainstorm progress" />
          <p className="text-sm text-muted">You can leave this page; the ideas will be here when you come back.</p>
        </Card>
      )}

      {session.data?.status === 'error' && (
        <Notice tone="error" title="This brainstorm did not finish">
          {session.data.error}
        </Notice>
      )}
      {session.data?.notes.map((note) => (
        <Notice key={note} tone="warn">
          {note}{' '}
          {note.includes('research') && (
            <button type="button" className="font-semibold underline" onClick={openResearch}>
              Open Research
            </button>
          )}
        </Notice>
      ))}

      {!sessions.data?.length && !busy && (
        <EmptyState icon={<Lightbulb className="size-8" />} title="No ideas yet">
          Pick how many ideas you want and start a brainstorm. Each idea comes with a title, a brief and an outline, ready to write.
        </EmptyState>
      )}

      {!!sessions.data?.length && (
        <div className="flex flex-wrap items-center gap-3">
          <Select
            aria-label="Brainstorm"
            className="w-auto max-w-full"
            value={sessionId ?? ''}
            onChange={(e) => {
              setPicked(Number(e.target.value))
              setOpenId(null)
            }}
          >
            {sessions.data.map((s) => (
              <option key={s.id} value={s.id}>
                {parseDate(s.created_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })} · {s.persona_name} · {s.ideas} ideas
              </option>
            ))}
          </Select>
          <Segmented label="Order ideas by" options={SORTS} value={sort} onChange={setSort} />
          <Segmented label="Show ideas" options={FILTERS.map((f) => ({ ...f, count: filterIdeas(ideas, f.id).length }))} value={filter} onChange={setFilter} />
          {sessionId && !running && (
            <button
              type="button"
              className="ml-auto rounded-md p-1.5 text-muted hover:bg-danger-soft hover:text-danger"
              aria-label="Delete this brainstorm"
              onClick={() => {
                if (
                  confirm('Delete this brainstorm? Saved ideas stay in your saved bank, and every idea it proposed is remembered so it is not suggested again.')
                )
                  deleteSession.mutate(sessionId, { onSuccess: () => setPicked(null) })
              }}
            >
              <Trash2 className="size-4" />
            </button>
          )}
        </div>
      )}

      {session.isLoading && <Spinner />}
      {session.data?.status === 'ready' && shown.length === 0 && (
        <p className="text-sm text-muted">{filter === 'open' ? 'Every idea here is written or dismissed.' : 'Nothing here yet.'}</p>
      )}
      {groups.map((group) => (
        <section key={group.key} aria-label={group.label} className="space-y-3">
          {sort !== 'best' && (
            <div>
              <h2 className="flex items-center gap-2 text-lg font-bold">
                {sort === 'theme' ? <FileText className="size-4 text-accent" aria-hidden /> : <Lightbulb className="size-4 text-accent" aria-hidden />}
                {group.label} <span className="text-sm font-normal text-muted">({group.ideas.length})</span>
              </h2>
              {group.hint && <p className="text-sm text-muted">{group.hint}</p>}
            </div>
          )}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {group.ideas.map((idea) => (
              <IdeaCard key={idea.id} idea={idea} onOpen={() => setOpenId(idea.id)} onState={(state) => updateIdea.mutate({ id: idea.id, body: { state } })} />
            ))}
          </div>
        </section>
      ))}

      <IdeaDialog idea={opened} personas={personas} onClose={() => setOpenId(null)} />
    </div>
  )
}
