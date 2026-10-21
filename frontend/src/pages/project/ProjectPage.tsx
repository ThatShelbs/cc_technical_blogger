import { useQueryClient } from '@tanstack/react-query'
import { Eye, FileDown, PencilLine, RefreshCw, Save, Wand2 } from 'lucide-react'
import { useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router'

import { errorText } from '../../api/client'
import { keys, useProject, useProjectMutations } from '../../api/hooks'
import type { ProjectOut } from '../../api/types.gen'
import { useJob, type Critique } from '../../api/useJob'
import { Article } from '../../components/Article'
import { Badge, Button, Card, Dialog, Field, Notice, Spinner, Textarea } from '../../components/ui'
import { cx } from '../../lib/cx'
import { ExportDialog } from './ExportDialog'
import { GenerationView } from './GenerationView'
import { ImageCard } from './ImageCard'

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

function TitlePicker({ project }: { project: ProjectOut }) {
  const { update } = useProjectMutations(project.id)
  const options = ((project.plan?.title_options as string[] | undefined) ?? []).filter(Boolean)
  if (!options.length) return null
  return (
    <Card className="space-y-2">
      <h2 className="font-bold">Title options</h2>
      <ul className="space-y-1.5">
        {options.map((title) => (
          <li key={title}>
            <button
              type="button"
              onClick={() => update.mutate({ title })}
              className={cx(
                'w-full rounded-lg border px-3 py-2 text-left text-sm',
                title === project.title ? 'border-accent bg-accent-soft font-semibold' : 'border-line hover:bg-surface-2',
              )}
              aria-pressed={title === project.title}
            >
              {title}
            </button>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function DialsSummary({ project }: { project: ProjectOut }) {
  const d = project.resolved_dials as Record<string, string | number>
  if (!d || !d.target_words) return null
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
        <span className="text-muted">Topic:</span> {d.topic}
      </p>
    </Card>
  )
}

function Editor({ project, onRegenerate }: { project: ProjectOut; onRegenerate: () => void }) {
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
                  disabled={!selection.trim() || dirty}
                  onClick={() => setRewriteOpen(true)}
                  title={dirty ? 'Save your edits first' : 'Select text in the editor first'}
                >
                  Rewrite selection
                </Button>
                <Button
                  size="sm"
                  icon={<Save className="size-4" />}
                  disabled={!dirty}
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
        <TitlePicker project={project} />
        <FidelityPanel project={project} />
        <DialsSummary project={project} />
        <Card className="space-y-2">
          <h2 className="font-bold">Start over</h2>
          <p className="text-sm text-muted">Write the whole post again from the same prompt and settings. Your current text and images are replaced.</p>
          <Button
            variant="secondary"
            icon={<RefreshCw className="size-4" />}
            onClick={() => {
              if (confirm('Regenerate the whole post? The current text and images will be replaced.')) onRegenerate()
            }}
          >
            Regenerate post
          </Button>
        </Card>
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
  const jobId = params.get('job') ?? project?.active_job_id ?? null

  const job = useJob(jobId, () => {
    void qc.invalidateQueries({ queryKey: keys.project(id) })
    void qc.invalidateQueries({ queryKey: keys.projects })
    setParams({}, { replace: true })
  })

  if (isLoading) return <Spinner />
  if (error || !project) return <Notice tone="error">{error ? errorText(error) : 'Post not found.'}</Notice>

  const generating = !!jobId && job.status !== 'succeeded' && job.status !== 'failed'
  const regenerate = () => generate.mutate(undefined, { onSuccess: (j) => setParams({ job: j.id }, { replace: true }) })

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
      {job.status === 'failed' && (
        <div className="mb-6">
          <Notice tone="error" title="Generation stopped">
            {job.error}
          </Notice>
        </div>
      )}
      {project.status === 'error' && !generating && job.status !== 'failed' && project.error && (
        <div className="mb-6">
          <Notice tone="error" title="The last generation failed">
            {project.error}
          </Notice>
        </div>
      )}
      {generating ? (
        <GenerationView job={job} />
      ) : project.markdown ? (
        <Editor project={project} onRegenerate={regenerate} />
      ) : (
        <Card className="space-y-4">
          <p className="whitespace-pre-wrap text-muted">{project.prompt}</p>
          {generate.error && <Notice tone="error">{errorText(generate.error)}</Notice>}
          <Button variant="flame" onClick={regenerate} loading={generate.isPending}>
            Write this post
          </Button>
        </Card>
      )}
    </>
  )
}
