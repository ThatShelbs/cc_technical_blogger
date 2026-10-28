import { History, MessageSquareText, RefreshCw, SlidersHorizontal, Undo2 } from 'lucide-react'
import { useState } from 'react'

import { errorText } from '../../api/client'
import { useProjectMutations } from '../../api/hooks'
import type { JobOut, ProjectOut } from '../../api/types.gen'
import { Button, Card, Field, Notice, Textarea } from '../../components/ui'

/** The brief (prompt or outline) this post was written from, with a way into its settings. */
export function BriefCard({ project, onEdit, disabled }: { project: ProjectOut; onEdit: () => void; disabled?: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const long = project.prompt.split('\n').length > 4 || project.prompt.length > 240
  return (
    <Card className="space-y-2">
      <h2 className="font-bold">Brief</h2>
      <p className={`text-sm whitespace-pre-wrap text-muted ${expanded || !long ? '' : 'line-clamp-4'}`}>{project.prompt}</p>
      {long && (
        <button type="button" className="text-sm font-semibold text-accent" onClick={() => setExpanded((v) => !v)} aria-expanded={expanded}>
          {expanded ? 'Show less' : 'Show all'}
        </button>
      )}
      <Button size="sm" variant="secondary" icon={<SlidersHorizontal className="size-4" />} onClick={onEdit} disabled={disabled}>
        Edit brief & settings
      </Button>
    </Card>
  )
}

/** Three ways to revise: tweak with feedback (keeps text and images), new settings, or start over. */
export function ReviseCard({
  project,
  dirty,
  busy,
  onTweakStarted,
  onOpenSettings,
  onRegenerate,
}: {
  project: ProjectOut
  dirty: boolean
  busy: boolean
  onTweakStarted: (job: JobOut) => void
  onOpenSettings: () => void
  onRegenerate: () => void
}) {
  const { tweak } = useProjectMutations(project.id)
  const [feedback, setFeedback] = useState('')
  const ready = feedback.trim().length >= 3 && !dirty && !busy
  return (
    <Card className="space-y-3">
      <h2 className="font-bold">Revise</h2>
      <form
        className="space-y-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (!ready) return
          tweak.mutate(feedback.trim(), {
            onSuccess: (job) => {
              setFeedback('')
              onTweakStarted(job)
            },
          })
        }}
      >
        <Field label="Tweak with feedback" hint="Keeps your text and images; only changes what you mention." htmlFor="tweak-feedback">
          <Textarea
            id="tweak-feedback"
            rows={4}
            value={feedback}
            maxLength={4000}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Shorter intro. Add a concrete example to the second section. The diagram should show the retry loop."
          />
        </Field>
        {tweak.error && <Notice tone="error">{errorText(tweak.error)}</Notice>}
        <Button
          type="submit"
          variant="flame"
          size="sm"
          icon={<MessageSquareText className="size-4" />}
          disabled={!ready}
          loading={tweak.isPending}
          title={dirty ? 'Save your edits first' : undefined}
        >
          Apply feedback
        </Button>
      </form>
      <div className="space-y-2 border-t border-line pt-3">
        <p className="text-sm text-muted">Or write it again. The current text and images are replaced; pinned titles are kept.</p>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" icon={<SlidersHorizontal className="size-4" />} onClick={onOpenSettings} disabled={busy}>
            Change settings & regenerate
          </Button>
          <Button
            size="sm"
            variant="ghost"
            icon={<RefreshCw className="size-4" />}
            disabled={busy}
            onClick={() => {
              if (confirm('Regenerate the whole post? The current text and images will be replaced.')) onRegenerate()
            }}
          >
            Regenerate post
          </Button>
        </div>
      </div>
    </Card>
  )
}

const KIND_LABEL: Record<string, string> = { tweak: 'Before feedback', rewrite: 'Before rewrite', edit: 'Before edit', restore: 'Before restore' }

function when(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

/** Earlier text versions: undo the last change or restore any of the last ten. */
export function HistoryCard({ project, busy, dirty }: { project: ProjectOut; busy: boolean; dirty: boolean }) {
  const { restoreRevision } = useProjectMutations(project.id)
  const revisions = project.revisions
  if (!revisions.length) return null
  const disabled = busy || dirty || restoreRevision.isPending
  return (
    <Card className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-bold">History</h2>
        <Button
          size="sm"
          variant="secondary"
          icon={<Undo2 className="size-4" />}
          disabled={disabled}
          loading={restoreRevision.isPending && restoreRevision.variables === 0}
          onClick={() => restoreRevision.mutate(0)}
          title={dirty ? 'Save or discard your edits first' : 'Restore the text as it was before the last change'}
        >
          Undo last change
        </Button>
      </div>
      <details className="text-sm">
        <summary className="inline-flex cursor-pointer items-center gap-1.5 text-muted">
          <History className="size-4" aria-hidden /> Earlier versions ({revisions.length})
        </summary>
        <ul className="mt-2 space-y-2">
          {revisions.map((rev) => (
            <li key={`${rev.index}-${rev.created_at}`} className="flex items-start justify-between gap-2 rounded-lg border border-line p-2">
              <div className="min-w-0">
                <p className="font-semibold">{KIND_LABEL[rev.kind] ?? 'Earlier version'}</p>
                {rev.label && (
                  <p className="truncate text-muted" title={rev.label}>
                    {rev.label}
                  </p>
                )}
                <p className="text-xs text-muted">
                  {when(rev.created_at)} · {rev.word_count.toLocaleString()} words
                </p>
              </div>
              <Button size="sm" variant="ghost" disabled={disabled} onClick={() => restoreRevision.mutate(rev.index)}>
                Restore
              </Button>
            </li>
          ))}
        </ul>
      </details>
      <p className="text-xs text-muted">Restoring keeps the current text as a version too. Images are not affected; each image has its own history.</p>
      {restoreRevision.error && <Notice tone="error">{errorText(restoreRevision.error)}</Notice>}
    </Card>
  )
}
