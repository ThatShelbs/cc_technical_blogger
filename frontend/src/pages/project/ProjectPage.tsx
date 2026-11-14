import { useQueryClient } from '@tanstack/react-query'
import { Dices, Eye, FileDown, PencilLine, Pin, RefreshCw, Save } from 'lucide-react'
import { useRef, useState, type ReactNode } from 'react'
import { useParams, useSearchParams } from 'react-router'

import { errorText } from '../../api/client'
import { keys, useABTestMutations, usePersonas, useProject, useProjectMutations } from '../../api/hooks'
import type { JobOut, ProjectOut } from '../../api/types.gen'
import { useJob, type Critique, type JobState } from '../../api/useJob'
import { Article } from '../../components/Article'
import { SectionActions, SectionToolbar, type SectionAction, type SectionRun } from '../../components/SectionToolbar'
import { Badge, Button, Card, Input, Notice, ProgressBar, Spinner, Textarea } from '../../components/ui'
import { cx } from '../../lib/cx'
import { referenceForHref } from '../../lib/references'
import { ABCompare } from './ab/ABCompare'
import { ABGenerationView } from './ab/ABGenerationView'
import { ABReveal } from './ab/ABReveal'
import { AuthenticityPanel } from './AuthenticityPanel'
import { BrandKitCard } from './BrandKitCard'
import { EvolutionCard } from './EvolutionCard'
import { ExportDialog } from './ExportDialog'
import { GenerationView } from './GenerationView'
import { ImageCard } from './ImageCard'
import { ReferenceLink, ReferencesCard } from './ReferencesCard'
import { useReferenceActions } from './useReferenceActions'
import { PostSettingsDialog } from './PostSettingsDialog'
import { BriefCard, HistoryCard, ReviseCard } from './RevisePanel'
import { StageControl } from './StageControl'

const REFERENCE_JOBS = ['enrich_post', 'redraw_reference']
const FAILED_TITLE: Record<string, string> = {
  tweak_post: 'Could not apply your feedback',
  enrich_post: 'Could not add references',
  redraw_reference: 'Could not redraw that reference',
}

const SCORE_LABELS: [keyof Critique, string][] = [
  ['voice', 'Sounds like you'],
  ['tone', 'Tone'],
  ['structure', 'Structure'],
  ['humor_match', 'Humor level'],
  ['education_match', 'Education level'],
  ['skimmability', 'Skimmable'],
  ['image_placement', 'Image placement'],
  ['callbacks', 'Callbacks'],
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
          {/* Posts written before a score existed (e.g. callbacks) simply do not show it. */}
          {SCORE_LABELS.filter(([key]) => critique[key] != null).map(([key, label]) => (
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

function DialsSummary({ project, onEdit, disabled }: { project: ProjectOut; onEdit: () => void; disabled: boolean }) {
  const { data: personas } = usePersonas()
  const d = project.resolved_dials as Record<string, string | number>
  if (!d || !d.target_words) return null
  const persona = personas?.find((p) => p.id === project.persona_id)
  return (
    <Card className="space-y-1 text-sm">
      <h2 className="mb-1 font-bold">Settings used</h2>
      <p>
        <span className="text-muted">Length:</span> ~{Number(d.target_words).toLocaleString()} words · <span className="text-muted">Images:</span>{' '}
        {d.image_count} · <span className="text-muted">References:</span> {d.reference_count ?? 0}
      </p>
      <p>
        <span className="text-muted">Humor:</span> {d.humor}/10 · <span className="text-muted">Level:</span> {d.education}
      </p>
      <p>
        <span className="text-muted">Story:</span> {d.storytelling} · <span className="text-muted">Opinion:</span> {d.opinion} ·{' '}
        <span className="text-muted">Formality:</span> {d.formality} · <span className="text-muted">Depth:</span> {d.technical_depth} ·{' '}
        <span className="text-muted">Skim:</span> {d.skimmability}
      </p>
      {d.opening_label && (
        <p>
          <span className="text-muted">Opening image:</span> {d.opening_label}
          {d.opening_note ? ` · "${d.opening_note}"` : ''}
        </p>
      )}
      {d.formula_label && (
        <p>
          <span className="text-muted">Formula:</span> {d.formula_label}
          {d.article_type_detected ? ' (type read from your brief)' : ''}
        </p>
      )}
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
      <Button
        size="sm"
        variant="ghost"
        icon={<Dices className="size-4" />}
        disabled={disabled}
        title="Open the settings, shuffle or change the formula, and regenerate"
        onClick={onEdit}
      >
        Try another formula
      </Button>
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
  /** Write the post twice and compare them blind (A/B Test Mode). */
  onABTest: () => void
  onOpenSettings: () => void
  onTweakStarted: (job: JobOut) => void
}

function Editor({ project, banner, busy, onRegenerate, onABTest, onOpenSettings, onTweakStarted }: EditorProps) {
  const { update, rewrite } = useProjectMutations(project.id)
  const referenceActions = useReferenceActions(project.id, { busy, onJobStarted: onTweakStarted })
  const [mode, setMode] = useState<'preview' | 'markdown'>('preview')
  const [text, setText] = useState(project.markdown)
  const [selection, setSelection] = useState('')
  const [pendingAction, setPendingAction] = useState<SectionAction | null>(null)
  const [exportOpen, setExportOpen] = useState(false)
  const textarea = useRef<HTMLTextAreaElement>(null)
  const preview = useRef<HTMLDivElement>(null)
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

  /** Regenerate one highlighted section; `source` is the exact slice of the post's Markdown. */
  const regenerate = (source: string, { action, instruction }: SectionRun) => {
    setPendingAction(action)
    rewrite.mutate(
      { selection: source, action, instruction },
      {
        onSuccess: () => {
          setSelection('')
          window.getSelection()?.removeAllRanges()
        },
        onSettled: () => setPendingAction(null),
      },
    )
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
          <Card padded={false} className="relative p-6 sm:p-10">
            <div ref={preview}>
              <Article
                markdown={project.markdown}
                images={project.images}
                renderImage={(_slot, image) => (image ? <ImageCard key={image.id} projectId={project.id} image={image} /> : null)}
                renderLink={(href, children) => {
                  const reference = referenceForHref(project.references, href)
                  return reference ? (
                    <ReferenceLink reference={reference} actions={referenceActions}>
                      {children}
                    </ReferenceLink>
                  ) : undefined
                }}
              />
            </div>
            <SectionToolbar container={preview} markdown={project.markdown} pending={pendingAction} disabled={busy} onRun={regenerate} />
          </Card>
        ) : (
          <Card padded={false} className="space-y-2 p-3">
            <p className="px-1 text-xs text-muted">
              Keep <code>{'{{image:…}}'}</code> lines where images belong. Select a passage to rewrite, compact, expand or add a source or quote.
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
            {selection.trim() && (
              <div className="rounded-lg border border-line bg-sunken p-2">
                {dirty ? (
                  <p className="px-2 py-1 text-sm text-muted">Save your edits first, then regenerate the selection.</p>
                ) : (
                  <SectionActions pending={pendingAction} disabled={busy} onRun={(run) => regenerate(selection, run)} />
                )}
              </div>
            )}
          </Card>
        )}
        {update.error && <Notice tone="error">{errorText(update.error)}</Notice>}
        {rewrite.error && <Notice tone="error">{errorText(rewrite.error)}</Notice>}
      </div>

      <aside className="space-y-4">
        <ReviseCard
          project={project}
          dirty={dirty}
          busy={busy}
          onTweakStarted={onTweakStarted}
          onOpenSettings={onOpenSettings}
          onRegenerate={onRegenerate}
          onABTest={onABTest}
        />
        <EvolutionCard project={project} />
        <ReferencesCard project={project} actions={referenceActions} />
        <HistoryCard project={project} busy={busy} dirty={dirty} />
        <TitlePicker project={project} />
        <BrandKitCard project={project} disabled={busy} />
        <AuthenticityPanel project={project} />
        <FidelityPanel project={project} />
        <BriefCard project={project} onEdit={onOpenSettings} disabled={busy} />
        <DialsSummary project={project} onEdit={onOpenSettings} disabled={busy} />
      </aside>

      <ExportDialog
        projectId={project.id}
        open={exportOpen}
        onClose={() => setExportOpen(false)}
        initial={String((project.resolved_dials as Record<string, unknown>)?.platform ?? 'medium')}
      />
    </div>
  )
}

export function ProjectPage() {
  const id = Number(useParams().id)
  const [params, setParams] = useSearchParams()
  const qc = useQueryClient()
  const { data: project, isLoading, error } = useProject(id)
  const { data: allPersonas } = usePersonas()
  const { generate } = useProjectMutations(id)
  const { start: startAB } = useABTestMutations(id, undefined)
  const [settingsOpen, setSettingsOpen] = useState(false)
  // The last finished job, kept after the URL is cleared so its outcome can be shown.
  const [finished, setFinished] = useState<{ kind: string; state: JobState } | null>(null)
  const jobId = params.get('job') ?? project?.active_job_id ?? null
  const jobKind = params.get('kind') ?? project?.active_job_kind ?? 'generate_post'

  const job = useJob(jobId, (state) => {
    void qc.invalidateQueries({ queryKey: keys.project(id) })
    void qc.invalidateQueries({ queryKey: keys.projects })
    // An A/B job changes its test: the choice, the reveal, the parts taken.
    void qc.invalidateQueries({ queryKey: ['ab-tests'] })
    setFinished({ kind: jobKind, state })
    setParams({}, { replace: true })
  })

  if (isLoading) return <Spinner />
  if (error || !project) return <Notice tone="error">{error ? errorText(error) : 'Post not found.'}</Notice>

  const running = !!jobId && job.status !== 'succeeded' && job.status !== 'failed'
  // Only a full generation takes over the page; other text jobs (feedback, references) show a banner over the editor.
  const generating = running && jobKind === 'generate_post'
  // An A/B test takes over the page until a winner is picked: two posts being written, then the blind choice.
  const abWriting = running && jobKind === 'ab_generate'
  const abDeciding = running && jobKind === 'ab_decide'
  const abTest = project.ab_test
  const abOpen = !!abTest && ['voting', 'error', 'generating', 'deciding'].includes(abTest.status)
  const tweaking = running && jobKind === 'tweak_post'
  const referencing = running && REFERENCE_JOBS.includes(jobKind)
  const follow = (j: JobOut) => {
    setFinished(null)
    setParams({ job: j.id, kind: j.kind }, { replace: true })
  }
  const regenerate = () => generate.mutate(undefined, { onSuccess: follow })
  const runABTest = () => startAB.mutate(undefined, { onSuccess: follow })
  const failed = finished?.state.status === 'failed' ? finished : null

  let banner: ReactNode = null
  if (abDeciding) {
    banner = (
      <Card className="space-y-2">
        <p className="text-sm font-semibold">Making your pick the post…</p>
        <ProgressBar value={job.progress} label="A/B decision progress" />
        <p className="text-xs text-muted">{job.message || 'Starting'}</p>
      </Card>
    )
  } else if (finished?.kind === 'ab_decide' && finished.state.status === 'succeeded' && finished.state.result?.notes_error) {
    banner = (
      <Notice tone="warn" title="Your blend note could not be applied">
        {String(finished.state.result.notes_error)} Try it again with “Tweak with feedback”.
      </Notice>
    )
  } else if (tweaking || referencing) {
    const what = tweaking ? 'Applying your feedback…' : jobKind === 'enrich_post' ? 'Finding references…' : 'Finding a new reference…'
    banner = (
      <Card className="space-y-2">
        <p className="text-sm font-semibold">{what}</p>
        <ProgressBar value={job.progress} label={tweaking ? 'Feedback progress' : 'References progress'} />
        <p className="text-xs text-muted">{job.message || 'Starting'}</p>
      </Card>
    )
  } else if (finished?.kind === 'enrich_post' && finished.state.status === 'succeeded') {
    const added = Number(finished.state.result?.added ?? 0)
    banner = (
      <Notice tone="success" title={`Added ${added} reference${added === 1 ? '' : 's'}`}>
        Each one is marked next to its link in the post. Not quite right? Redraw it, or use “Undo last change”.
      </Notice>
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
        {abWriting || abOpen ? (
          <Badge tone="accent">A/B test</Badge>
        ) : generating || project.status === 'generating' ? (
          <Badge tone="accent">Writing…</Badge>
        ) : project.status === 'error' ? (
          <Badge tone="danger">Needs attention</Badge>
        ) : project.markdown ? (
          <StageControl project={project} disabled={running} />
        ) : null}
      </div>
      {allPersonas?.find((p) => p.id === project.persona_id)?.is_example && (
        <div className="mb-6">
          <Notice title="This is an example post">
            It was built offline to show what Proseferno produces: the illustrations are placeholders and no Claude call was made. Set up your own persona to
            write in your voice, then remove the example from the Personas page.
          </Notice>
        </div>
      )}
      {failed && (
        <div className="mb-6">
          <Notice tone="error" title={FAILED_TITLE[failed.kind] ?? 'Generation stopped'}>
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
      ) : abWriting ? (
        <ABGenerationView job={job} />
      ) : abDeciding && !project.markdown ? (
        banner
      ) : abOpen && abTest && !abDeciding ? (
        <ABCompare projectId={project.id} testId={abTest.id} onStarted={follow} />
      ) : project.markdown ? (
        <Editor
          project={project}
          banner={
            <>
              {abTest?.status === 'decided' && !abDeciding && <ABReveal projectId={project.id} testId={abTest.id} />}
              {banner}
            </>
          }
          busy={tweaking || referencing || abDeciding}
          onRegenerate={regenerate}
          onABTest={runABTest}
          onOpenSettings={() => setSettingsOpen(true)}
          onTweakStarted={follow}
        />
      ) : (
        <Card className="space-y-4">
          <p className="whitespace-pre-wrap text-muted">{project.prompt}</p>
          {(generate.error || startAB.error) && <Notice tone="error">{errorText(generate.error ?? startAB.error)}</Notice>}
          <div className="flex flex-wrap gap-2">
            <Button variant="flame" onClick={regenerate} loading={generate.isPending}>
              Write this post
            </Button>
            <Button variant="secondary" onClick={runABTest} loading={startAB.isPending}>
              Write two versions (A/B test)
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
