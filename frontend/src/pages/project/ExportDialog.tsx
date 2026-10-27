import { Check, ClipboardCopy, Download, Sparkles } from 'lucide-react'
import { useState } from 'react'

import { errorText } from '../../api/client'
import { fetchCopyHtml, useLinkedInPost, useWriteLinkedInPost } from '../../api/hooks'
import { Button, Dialog, Notice, Textarea } from '../../components/ui'
import { cx } from '../../lib/cx'

const POST_LIMIT = 3000
const SEE_MORE_AT = 210

const PLATFORMS = [
  {
    id: 'medium',
    name: 'Medium',
    tip: 'Copy, then paste into a new Medium story. Headings map to Medium’s large and small headings; the hero image becomes the preview.',
  },
  {
    id: 'substack',
    name: 'Substack',
    tip: 'Paste the title and subtitle into Substack’s fields (they are in the zip README), then paste the body. Use thumbnail.png as the social preview.',
  },
  {
    id: 'linkedin',
    name: 'LinkedIn',
    tip: 'Paste into “Write article” with the 1920×1080 cover. The zip adds a feed post and a swipeable document carousel (PDF + editable PowerPoint).',
  },
  { id: 'gumroad', name: 'Gumroad', tip: 'The zip includes a print-ready PDF plus an HTML version and a cover image.' },
  { id: 'markdown', name: 'Markdown', tip: 'Front matter for dev.to, Hashnode, Ghost or a static site, plus a Word version.' },
] as const

const COPYABLE = new Set(['medium', 'substack', 'linkedin'])

function useCopied() {
  const [copied, setCopied] = useState<string | null>(null)
  const flash = (what: string) => {
    setCopied(what)
    setTimeout(() => setCopied(null), 2500)
  }
  return [copied, flash] as const
}

function LinkedInPost({ projectId }: { projectId: number }) {
  const post = useLinkedInPost(projectId, true)
  const write = useWriteLinkedInPost(projectId)
  const [draft, setDraft] = useState<string | null>(null)
  const [copied, flash] = useCopied()
  const text = draft ?? post.data?.text ?? ''

  return (
    <div className="space-y-2 rounded-xl border border-line p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold">Feed post</p>
        <span className={cx('text-xs tabular-nums', text.length > POST_LIMIT ? 'text-danger' : 'text-muted')}>
          {text.length.toLocaleString()} / {POST_LIMIT.toLocaleString()}
        </span>
      </div>
      <p className="text-xs text-muted">
        {post.data?.written_by === 'claude' ? 'Written by Claude in your voice.' : 'A starter built from your article. Let Claude write one in your voice.'} The
        first ~{SEE_MORE_AT} characters show before “…see more”.
      </p>
      <Textarea aria-label="LinkedIn feed post" rows={9} className="text-sm" value={text} onChange={(e) => setDraft(e.target.value)} />
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          icon={<Sparkles className="size-4" />}
          loading={write.isPending}
          onClick={() => write.mutate(undefined, { onSuccess: () => setDraft(null) })}
        >
          {post.data?.written_by === 'claude' ? 'Rewrite with Claude' : 'Write with Claude'}
        </Button>
        <Button
          size="sm"
          variant="secondary"
          icon={copied ? <Check className="size-4" /> : <ClipboardCopy className="size-4" />}
          disabled={!text}
          onClick={async () => {
            await navigator.clipboard.writeText(text)
            flash('post')
          }}
        >
          {copied ? 'Copied!' : 'Copy post'}
        </Button>
      </div>
      {(write.error || post.error) && <Notice tone="error">{errorText(write.error ?? post.error)}</Notice>}
    </div>
  )
}

export function ExportDialog({ projectId, open, onClose, initial = 'medium' }: { projectId: number; open: boolean; onClose: () => void; initial?: string }) {
  const [platform, setPlatform] = useState<string>(initial)
  const [copied, flash] = useCopied()
  const [error, setError] = useState<string | null>(null)
  const [copying, setCopying] = useState(false)
  const current = PLATFORMS.find((p) => p.id === platform) ?? PLATFORMS[0]

  const copy = async () => {
    setError(null)
    setCopying(true)
    try {
      const { html } = await fetchCopyHtml(projectId, platform)
      const plain = new DOMParser().parseFromString(html, 'text/html').body.innerText
      await navigator.clipboard.write([
        new ClipboardItem({ 'text/html': new Blob([html], { type: 'text/html' }), 'text/plain': new Blob([plain], { type: 'text/plain' }) }),
      ])
      flash('article')
    } catch (e) {
      setError(errorText(e))
    } finally {
      setCopying(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Export your post" wide={platform === 'linkedin'}>
      <div className="space-y-5">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Platform">
          {PLATFORMS.map((p) => (
            <button
              key={p.id}
              type="button"
              role="radio"
              aria-checked={platform === p.id}
              onClick={() => setPlatform(p.id)}
              className={cx(
                'rounded-xl border px-4 py-3 text-left font-semibold',
                platform === p.id ? 'border-accent bg-accent-soft' : 'border-line hover:bg-surface-2',
              )}
            >
              {p.name}
            </button>
          ))}
        </div>
        <p className="text-sm text-muted">{current.tip}</p>
        <div className="flex flex-wrap gap-2">
          {COPYABLE.has(platform) && (
            <Button icon={copied ? <Check className="size-4" /> : <ClipboardCopy className="size-4" />} onClick={copy} loading={copying}>
              {copied ? 'Copied!' : platform === 'linkedin' ? 'Copy article for LinkedIn' : `Copy for ${current.name}`}
            </Button>
          )}
          <a href={`/api/projects/${projectId}/export/${platform}`} download>
            <Button variant={COPYABLE.has(platform) ? 'secondary' : 'primary'} icon={<Download className="size-4" />}>
              Download bundle (.zip)
            </Button>
          </a>
        </div>
        {error && <Notice tone="error">Could not copy: {error}. Download the bundle instead.</Notice>}
        {platform === 'linkedin' && open && <LinkedInPost projectId={projectId} />}
      </div>
    </Dialog>
  )
}
