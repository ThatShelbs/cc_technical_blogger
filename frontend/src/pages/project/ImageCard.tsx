import { useQueryClient } from '@tanstack/react-query'
import { Dices, History, ImagePlus, Lightbulb, PencilLine } from 'lucide-react'
import { useRef, useState } from 'react'

import { errorText } from '../../api/client'
import { keys, useImageMutations } from '../../api/hooks'
import type { ImageOut } from '../../api/types.gen'
import { useJob } from '../../api/useJob'
import { fullCaption } from '../../lib/article'
import { Badge, Button, Dialog, Field, Input, Notice, Spinner } from '../../components/ui'
import { cx } from '../../lib/cx'

const PROVIDER_LABEL: Record<string, string> = {
  'claude-svg': 'Claude SVG',
  'vega-lite': 'Claude + Vega-Lite',
  placeholder: 'Placeholder',
  upload: 'Your upload',
}

const KIND_LABEL: Record<string, string> = {
  hero: 'Hero · thumbnail',
  diagram: 'Diagram',
  chart: 'Chart',
  illustration: 'Illustration',
  icon: 'Icons',
  meme: 'Closing meme',
  screenshot: 'Screenshot',
}

export function ImageCard({ projectId, image }: { projectId: number; image: ImageOut }) {
  const qc = useQueryClient()
  const mutations = useImageMutations(projectId)
  const [jobId, setJobId] = useState<string | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [caption, setCaption] = useState(image.caption)
  const [alt, setAlt] = useState(image.alt)
  const [credit, setCredit] = useState(image.credit)
  const fileInput = useRef<HTMLInputElement>(null)

  const job = useJob(jobId, () => {
    setJobId(null)
    void qc.invalidateQueries({ queryKey: keys.project(projectId) })
  })
  const busy = !!jobId || mutations.upload.isPending
  const redraw = (rethink: boolean) => mutations.redraw.mutate({ id: image.id, rethink }, { onSuccess: (j) => setJobId(j.id) })

  return (
    <figure className="group my-8 font-sans not-italic">
      <div className="relative overflow-hidden rounded-xl border border-line bg-sunken">
        {image.url ? (
          <img src={image.url} alt={image.alt} className={cx('w-full', busy && 'opacity-40')} />
        ) : (
          <div className="flex aspect-video items-center justify-center p-6 text-center text-sm text-muted">
            {image.status === 'pending' ? <Spinner label="Creating image…" /> : image.purpose}
          </div>
        )}
        {busy && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="rounded-full bg-surface px-4 py-2 shadow">
              <Spinner label={job.message || 'Redrawing…'} />
            </span>
          </div>
        )}
        <div className="absolute top-2 left-2">
          <Badge tone="accent">{KIND_LABEL[image.kind] ?? image.kind}</Badge>
        </div>
      </div>

      {fullCaption(image) && <figcaption className="mt-2 text-center text-sm text-muted">{fullCaption(image)}</figcaption>}
      {image.status === 'error' && (
        <div className="mt-2">
          <Notice tone="error">{image.error}</Notice>
        </div>
      )}
      {job.status === 'failed' && (
        <div className="mt-2">
          <Notice tone="error">{job.error}</Notice>
        </div>
      )}
      {mutations.upload.error && (
        <div className="mt-2">
          <Notice tone="error">{errorText(mutations.upload.error)}</Notice>
        </div>
      )}
      {image.kind === 'screenshot' && image.status === 'placeholder' && (
        <p className="mt-2 text-center text-xs text-muted">Replace this placeholder with a real screenshot: {image.purpose}</p>
      )}

      <div className="mt-3 flex flex-wrap justify-center gap-2" aria-label={`Actions for ${KIND_LABEL[image.kind] ?? 'image'}`}>
        <Button
          size="sm"
          variant="secondary"
          icon={<Dices className="size-4" />}
          onClick={() => redraw(false)}
          disabled={busy}
          title="Claude draws the same idea a new way"
        >
          Redraw
        </Button>
        <Button
          size="sm"
          variant="secondary"
          icon={<Lightbulb className="size-4" />}
          onClick={() => redraw(true)}
          disabled={busy}
          title="Ask Claude for a different idea"
        >
          New idea
        </Button>
        <Button size="sm" variant="secondary" icon={<ImagePlus className="size-4" />} onClick={() => fileInput.current?.click()} disabled={busy}>
          Replace
        </Button>
        <Button
          size="sm"
          variant="ghost"
          icon={<PencilLine className="size-4" />}
          onClick={() => {
            setCaption(image.caption)
            setAlt(image.alt)
            setCredit(image.credit)
            setEditOpen(true)
          }}
        >
          Caption
        </Button>
        {image.history.length > 1 && (
          <Button size="sm" variant="ghost" icon={<History className="size-4" />} onClick={() => setHistoryOpen(true)}>
            Versions ({image.history.length})
          </Button>
        )}
        <input
          ref={fileInput}
          type="file"
          accept="image/*"
          className="hidden"
          aria-label="Upload replacement image"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) mutations.upload.mutate({ id: image.id, file })
            e.target.value = ''
          }}
        />
      </div>

      <Dialog open={historyOpen} onClose={() => setHistoryOpen(false)} title="Image versions" wide>
        <div className="grid gap-4 sm:grid-cols-2">
          {image.history.map((entry) => (
            <button
              key={entry.index}
              type="button"
              className="rounded-xl border border-line p-2 text-left hover:border-accent"
              onClick={() => mutations.revert.mutate({ id: image.id, index: entry.index }, { onSuccess: () => setHistoryOpen(false) })}
            >
              <img src={entry.url} alt={`Version ${entry.index + 1}`} className="w-full rounded-lg" />
              <p className="mt-1 text-xs text-muted">
                v{entry.index + 1} · {PROVIDER_LABEL[entry.provider] ?? entry.provider}{' '}
                {entry.created_at ? `· ${new Date(entry.created_at).toLocaleString()}` : ''}
              </p>
            </button>
          ))}
        </div>
      </Dialog>

      <Dialog open={editOpen} onClose={() => setEditOpen(false)} title="Caption and credit">
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault()
            mutations.update.mutate({ id: image.id, caption, alt, credit }, { onSuccess: () => setEditOpen(false) })
          }}
        >
          <Field label="Caption" htmlFor={`cap-${image.id}`}>
            <Input id={`cap-${image.id}`} value={caption} onChange={(e) => setCaption(e.target.value)} />
          </Field>
          <Field label="Credit" hint="Who made it and with what model or tool." htmlFor={`credit-${image.id}`}>
            <Input id={`credit-${image.id}`} value={credit} onChange={(e) => setCredit(e.target.value)} />
          </Field>
          <Field label="Alt text" hint="Describes the image for screen readers." htmlFor={`alt-${image.id}`}>
            <Input id={`alt-${image.id}`} value={alt} onChange={(e) => setAlt(e.target.value)} />
          </Field>
          <Button type="submit" loading={mutations.update.isPending}>
            Save
          </Button>
        </form>
      </Dialog>
    </figure>
  )
}
