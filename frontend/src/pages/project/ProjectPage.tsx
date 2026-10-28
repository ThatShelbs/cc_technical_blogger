import { useQueryClient } from '@tanstack/react-query'
import { Eye, FileDown, PencilLine, Pin, RefreshCw, Save, Wand2 } from 'lucide-react'
import { useRef, useState, type ReactNode } from 'react'
import { useParams, useSearchParams } from 'react-router'

import { errorText } from '../../api/client'
import { keys, usePersonas, useProject, useProjectMutations } from '../../api/hooks'
import type { JobOut, ProjectOut } from '../../api/types.gen'
import { useJob, type Critique, type JobState } from '../../api/useJob'
import { Article } from '../../components/Article'
import { Badge, Button, Card, Dialog, Field, Input, Notice, ProgressBar, Spinner, Textarea } from '../../components/ui'
import { cx } from '../../lib/cx'
import { AuthenticityPanel } from './AuthenticityPanel'
import { ExportDialog } from './ExportDialog'
import { GenerationView } from './GenerationView'
import { ImageCard } from './ImageCard'
import { PostSettingsDialog } from './PostSettingsDialog'
import { BriefCard, HistoryCard, ReviseCard } from './RevisePanel'

const SCORE_LABELS: [keyof Critique, string][] = [
  ['voice', 'Sounds like you'],
  ['tone', 'Tone'],
  ['structure', 'Structure'],
  ['humor_match', 'Humor level'],
  ['education_match', 'Education level'],
  ['skimmability', 'Skimmable'],
  ['image_placement', 'Image placement'],
]

function FidelityPanel({ project }: { project: ProjectOut }) {
  const critique = project.critique as Critique | null
  const score = project.fidelity?.score as number | null | undefined
  return (
    <Card className="space-y-3">
      <h2 className="font-bold">Voice fidelity</h2>
      {typeof score === 'number' && (
        <div>
          <p className="text-3xl font-extrabold tabular-nums">
            {Math.round(score)}
            <span className="text-base font-semibold text-muted">/100</span>
          </p>
          <p className="text-xs text-muted">Measured style match (sentence rhythm, paragraphs, questions, “I/you” rate, headings, images) vs. your posts.</p>
        </div>
      )}
      {critique && (
        <div className="space-y-1.5">
          <p className="text-sm font-semibold">Editor scores before the final revision</p>
          {SCORE_LABELS.map(([key, label]) => (
            <div key={key} className="flex items-center gap-2 text-sm">
              <span className="w-32 shrink-0 text-muted">{label}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
                <div className="flame-bar h-full" style={{ width: `${(Number(critique[key]) / 10) * 100}%` }} />
              </div>
              <span className="w-6 text-right tabular-nums">{String(critique[key])}</span>
            </div>
          ))}
        </div>
      )}
      {!critique && score == null && <p className="text-sm text-muted">Scores appear after the post is generated.</p>}
    </Card>
  )
}

export function TitlePicker({ project }: { project: ProjectOut }) {
  const { update, regenerateTitles } = useProjectMutations(project.id)
  const [draft, setDraft] = useState(project.title)
  // When the saved title changes (pick, save, regeneration), reset the edit box to it.
  const [savedTitle, setSavedTitle] = useState(project.title)
  if (savedTitle !== project.title) {
    setSavedTitle(project.title)
    setDraft(project.title)
  }
  const pinned = project.pinned_titles
  const planned = ((project.plan?.title_options as string[] | undefined) ?? []).filter(Boolean)
  // A hand-edited title is not one of the options; show it first so it stays selectable and pinnable.
  const options = project.title && !planned.includes(project.title) ? [project.title, ...planned] : planned
  if (!options.length) return null
  const dirty = draft.trim() !== '' && draft.trim() !== project.title
  const togglePin = (title: string) => update.mutate({ pinned_titles: pinned.includes(title) ? pinned.filter((t) => t !== title) : [...pinned, title] })

  return (
    <Card className="space-y-3">
      <h2 className="font-bold">Title</h2>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (dirty) update.mutate({ title: draft.trim() })
        }}
      >
        <Input value={draft} onChange={(e) => setDraft(e.target.value)} aria-label="Post title" className="min-w-0 flex-1 text-sm" />
        <Button type="submit" size="sm" disabled={!dirty} loading={update.isPending && dirty} aria-label="Save title">
          Save
        </Button>
      </form>

      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-muted">Options</h3>
        <Button
          size="sm"
          variant="ghost"
          icon={<RefreshCw className="size-4" />}
          loading={regenerateTitles.isPending}
          onClick={() => regenerateTitles.mutate()}
          title="Keeps your selected and pinned titles"
        >
          New options
        </Button>
      </div>
      <ul className="space-y-1.5">
        {options.map((title) => {
          const selected = title === project.title
          const isPinned = pinned.includes(title)
          return (
            <li key={title} className="flex items-stretch gap-1">
              <button
                type="button"
                onClick={() => update.mutate({ title })}
                className={cx(
                  'min-w-0 flex-1 rounded-lg border px-3 py-2 text-left text-sm',
                  selected ? 'border-accent bg-accent-soft font-semibold' : 'border-line hover:bg-surface-2',
                )}
                aria-pressed={selected}
              >
                {title}
              </button>
              <button
                type="button"
                onClick={() => togglePin(title)}
                className={cx('shrink-0 rounded-lg px-2', isPinned ? 'text-accent' : 'text-muted hover:text-fg')}
                aria-pressed={isPinned}
                aria-label={isPinned ? `Unpin “${title}”` : `Pin “${title}”`}
                title={isPinned ? 'Pinned: kept when you ask for new options' : 'Pin to keep it when you ask for new options'}
              >
                <Pin className={cx('size-4', isPinned && 'fill-current')} aria-hidden />
              </button>
            </li>
          )
        })}
      </ul>
      <p className="text-xs text-muted">“New options” keeps your selected and pinned titles.</p>
      {regenerateTitles.error && <Notice tone="error">{errorText(regenerateTitles.error)}</Notice>}
    </Card>
  )
}

function DialsSummary({ project }: { project: ProjectOut }) {
  const { data: personas } = usePersonas()
  const d = project.resolved_dials as Record<string, string | number>
  if (!d || !d.target_words) return null
  const persona = personas?.find((p) => p.id === project.persona_id)
  return (
    <Card className="space-y-1 text-sm">
      <h2 className="mb-1 font-bold">Settings used</h2>
      <p>
        <span className="text-muted">Length:</span> ~{Number(d.target_words).toLocaleString()} words · <span className="text-muted">Images:</span>{' '}
        {d.image_count}
      </p>
      <p>
        <span className="text-muted">Humor:</span> {d.humor}/10 · <span className="text-muted">Level:</span> {d.education}
      </p>
      <p>
        <span className="text-muted">Story:</span> {d.storytelling} · <span className="text-muted">Opinion:</span> {d.opinion} ·{' '}
        <span className="text-muted">Formality:</span> {d.formality} · <span className="text-muted">Depth:</span> {d.technical_depth} ·{' '}
        <span className="text-muted">Skim:</span> {d.skimmability}
      </p>
      <p>
        <span className="text-muted">Topic:</span> {d.topic} · <span className="text-muted">For:</span> {String(d.platform)}
      </p>
      {d.audience && (
        <p>
          <span className="text-muted">Audience:</span> {d.audience}
        </p>
      )}
      <p className="text-muted">
        {persona ? `${persona.name} · ` : ''}
        {project.voice_profile_version ? `voice profile v${project.voice_profile_version}` : ''}
      </p>
    </Card>
  )
}

interface EditorProps {
  project: ProjectOut
  /** Shown above the post, e.g. tweak progress or what the last tweak changed. */
  banner?: ReactNode
  /** A tweak is running: the post stays visible but cannot be changed. */
  busy: boolean
  onRegenerate: () => void
  onOpenSettings: () => void
  onTweakStarted: (job: JobOut) => void
}

function Editor({ project, banner, busy, onRegenerate, onOpenSettings, onTweakStarted }: EditorProps) {
  const { update, rewrite } = useProjectMutations(project.id)
  const [mode, setMode] = useState<'preview' | 'markdown'>('preview')
  const [text, setText] = useState(project.markdown)
  const [selection, setSelection] = useState('')
  const [rewriteOpen, setRewriteOpen] = useState(false)
  const [instruction, setInstruction] = useState('')
  const [exportOpen, setExportOpen] = useState(false)
  const textarea = useRef<HTMLTextAreaElement>(null)
  const dirty = text !== project.markdown

  // When the saved post changes (save, rewrite, title pick), reset the editor text to it.
  const [savedMarkdown, setSavedMarkdown] = useState(project.markdown)
  if (savedMarkdown !== project.markdown) {
    setSavedMarkdown(project.markdown)
    setText(project.markdown)
  }

  const captureSelection = () => {
    const el = textarea.current
    if (el) setSelection(el.value.slice(el.selectionStart, el.selectionEnd))
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="min-w-0 space-y-4">
        {banner}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="inline-flex rounded-lg border border-line bg-surface p-1" role="tablist" aria-label="Editor mode">
            {(
              [
                ['preview', 'Preview', Eye],
                ['markdown', 'Edit Markdown', PencilLine],
              ] as const
            ).map(([key, label, Icon]) => (
              <button
                key={key}
                role="tab"
                aria-selected={mode === key}
                onClick={() => setMode(key)}
                className={cx(
                  'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-semibold',
                  mode === key ? 'bg-accent-soft' : 'text-muted hover:text-fg',
                )}
              >
                <Icon className="size-4" aria-hidden /> {label}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {mode === 'markdown' && (
              <>
                <Button
                  size="sm"
                  variant="secondary"
                  icon={<Wand2 className="size-4" />}
                  disabled={!selection.trim() || dirty || busy}
                  onClick={() => setRewriteOpen(true)}
                  title={dirty ? 'Save your edits first' : 'Select text in the editor first'}
                >
                  Rewrite selection
                </Button>
                <Button
                  size="sm"
                  icon={<Save className="size-4" />}
                  disabled={!dirty || busy}
                  loading={update.isPending}
                  onClick={() => update.mutate({ markdown: text })}
                >
                  Save
                </Button>
              </>
            )}
            <Button size="sm" variant="flame" icon={<FileDown className="size-4" />} onClick={() => setExportOpen(true)} disabled={dirty}>
              Export
            </Button>
          </div>
        </div>

        {mode === 'preview' ? (
          <Card padded={false} className="p-6 sm:p-10">
            <Article
              markdown={project.markdown}
              images={project.images}
              renderImage={(_slot, image) => (image ? <ImageCard key={image.id} projectId={project.id} image={image} /> : null)}
            />
          </Card>
        ) : (
          <Card padded={false} className="space-y-2 p-3">
            <p className="px-1 text-xs text-muted">
              Keep <code>{'{{image:…}}'}</code> lines where images belong. Select a passage and choose “Rewrite selection” to have it rewritten in your voice.
            </p>
            <Textarea
              ref={textarea}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onSelect={captureSelection}
              rows={32}
              className="font-mono text-sm"
              aria-label="Post markdown"
            />
          </Card>
        )}
        {update.error && <Notice tone="error">{errorText(update.error)}</Notice>}
      </div>

      <aside className="space-y-4">
        <ReviseCard project={project} dirty={dirty} busy={busy} onTweakStarted={onTweakStarted} onOpenSettings={onOpenSettings} onRegenerate={onRegenerate} />
        <HistoryCard project={project} busy={busy} dirty={dirty} />
        <TitlePicker project={project} />
        <AuthenticityPanel project={project} />
        <FidelityPanel project={project} />
        <BriefCard project={project} onEdit={onOpenSettings} disabled={busy} />
        <DialsSummary project={project} />
      </aside>

      <ExportDialog
        projectId={project.id}
        open={exportOpen}
        onClose={() => setExportOpen(false)}
        initial={String((project.resolved_dials as Record<string, unknown>)?.platform ?? 'medium')}
      />
      <Dialog open={rewriteOpen} onClose={() => setRewriteOpen(false)} title="Rewrite selection">
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault()
            rewrite.mutate(
              { selection, instruction },
              {
                onSuccess: () => {
                  setRewriteOpen(false)
                  setInstruction('')
                  setSelection('')
                },
              },
            )
          }}
        >
          <blockquote className="max-h-40 overflow-auto rounded-lg border-l-4 border-accent bg-sunken p-3 text-sm whitespace-pre-wrap">{selection}</blockquote>
          <Field label="How should it change?" hint="Leave empty for “make it sound more like me”." htmlFor="rewrite-instruction">
            <Textarea
              id="rewrite-instruction"
              rows={3}
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="Punchier, add an analogy, explain it for beginners…"
            />
          </Field>
          {rewrite.error && <Notice tone="error">{errorText(rewrite.error)}</Notice>}
          <Button type="submit" loading={rewrite.isPending} icon={<Wand2 className="size-4" />}>
            Rewrite in my voice
          </Button>
        </form>
      </Dialog>
    </div>
  )
}

export function ProjectPage() {
  const id = Number(useParams().id)
  const [params, setParams] = useSearchParams()
  const qc = useQueryClient()
  const { data: project, isLoading, error } = useProject(id)
  const { generate } = useProjectMutations(id)
  const [settingsOpen, setSettingsOpen] = useState(false)
  // The last finished job, kept after the URL is cleared so its outcome can be shown.
  const [finished, setFinished] = useState<{ kind: string; state: JobState } | null>(null)
  const jobId = params.get('job') ?? project?.active_job_id ?? null
  const jobKind = params.get('kind') ?? project?.active_job_kind ?? 'generate_post'

  const job = useJob(jobId, (state) => {
    void qc.invalidateQueries({ queryKey: keys.project(id) })
    void qc.invalidateQueries({ queryKey: keys.projects })
    setFinished({ kind: jobKind, state })
    setParams({}, { replace: true })
  })

  if (isLoading) return <Spinner />
  if (error || !project) return <Notice tone="error">{error ? errorText(error) : 'Post not found.'}</Notice>

  const running = !!jobId && job.status !== 'succeeded' && job.status !== 'failed'
  const generating = running && jobKind !== 'tweak_post'
  const tweaking = running && jobKind === 'tweak_post'
  const follow = (j: JobOut) => {
    setFinished(null)
    setParams({ job: j.id, kind: j.kind }, { replace: true })
  }
  const regenerate = () => generate.mutate(undefined, { onSuccess: follow })
  const failed = finished?.state.status === 'failed' ? finished : null

  let banner: ReactNode = null
  if (tweaking) {
    banner = (
      <Card className="space-y-2">
        <p className="text-sm font-semibold">Applying your feedback…</p>
        <ProgressBar value={job.progress} label="Feedback progress" />
        <p className="text-xs text-muted">{job.message || 'Starting'}</p>
      </Card>
    )
  } else if (finished?.kind === 'tweak_post' && finished.state.status === 'succeeded') {
    const result = finished.state.result ?? {}
    const skipped = (result.skipped as string[] | undefined) ?? []
    banner = (
      <Notice tone="success" title="Feedback applied">
        {String(result.summary ?? 'Done.')}
        {skipped.length > 0 && ` ${skipped.length} edit${skipped.length > 1 ? 's' : ''} could not be placed; try quoting the sentence you mean.`} Not quite
        right? Use “Undo last change”.
      </Notice>
    )
  }

  return (
    <>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-muted">Post</p>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{project.title || 'Untitled post'}</h1>
        </div>
        <Badge tone={project.status === 'ready' ? 'success' : project.status === 'error' ? 'danger' : 'accent'}>
          {generating ? 'Writing…' : project.status}
        </Badge>
      </div>
      {failed && (
        <div className="mb-6">
          <Notice tone="error" title={failed.kind === 'tweak_post' ? 'Could not apply your feedback' : 'Generation stopped'}>
            {failed.state.error}
          </Notice>
        </div>
      )}
      {project.status === 'error' && !generating && !failed && project.error && (
        <div className="mb-6">
          <Notice tone="error" title="The last generation failed">
            {project.error}
          </Notice>
        </div>
      )}
      {generating ? (
        <GenerationView job={job} />
      ) : project.markdown ? (
        <Editor
          project={project}
          banner={banner}
          busy={tweaking}
          onRegenerate={regenerate}
          onOpenSettings={() => setSettingsOpen(true)}
          onTweakStarted={follow}
        />
      ) : (
        <Card className="space-y-4">
          <p className="whitespace-pre-wrap text-muted">{project.prompt}</p>
          {generate.error && <Notice tone="error">{errorText(generate.error)}</Notice>}
          <div className="flex flex-wrap gap-2">
            <Button variant="flame" onClick={regenerate} loading={generate.isPending}>
              Write this post
            </Button>
            <Button variant="secondary" onClick={() => setSettingsOpen(true)}>
              Edit brief & settings
            </Button>
          </div>
        </Card>
      )}
      <PostSettingsDialog
        project={project}
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onStarted={(j) => {
          setSettingsOpen(false)
          follow(j)
        }}
      />
    </>
  )
}
