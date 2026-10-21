import { Check, ClipboardCopy, Download } from 'lucide-react'
import { useState } from 'react'

import { errorText } from '../../api/client'
import { fetchCopyHtml } from '../../api/hooks'
import { Button, Dialog, Notice } from '../../components/ui'
import { cx } from '../../lib/cx'

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
  { id: 'gumroad', name: 'Gumroad', tip: 'The zip includes a print-ready PDF plus an HTML version and a cover image.' },
  { id: 'markdown', name: 'Markdown', tip: 'Front matter for dev.to, Hashnode, Ghost or a static site, plus a Word version.' },
] as const

export function ExportDialog({ projectId, open, onClose, initial = 'medium' }: { projectId: number; open: boolean; onClose: () => void; initial?: string }) {
  const [platform, setPlatform] = useState<string>(initial)
  const [copied, setCopied] = useState(false)
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
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    } catch (e) {
      setError(errorText(e))
    } finally {
      setCopying(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Export your post">
      <div className="space-y-5">
        <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Platform">
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
          {platform !== 'gumroad' && platform !== 'markdown' && (
            <Button icon={copied ? <Check className="size-4" /> : <ClipboardCopy className="size-4" />} onClick={copy} loading={copying}>
              {copied ? 'Copied!' : `Copy for ${current.name}`}
            </Button>
          )}
          <a href={`/api/projects/${projectId}/export/${platform}`} download>
            <Button variant={platform === 'gumroad' || platform === 'markdown' ? 'primary' : 'secondary'} icon={<Download className="size-4" />}>
              Download bundle (.zip)
            </Button>
          </a>
        </div>
        {error && <Notice tone="error">Could not copy: {error}. Download the bundle instead.</Notice>}
      </div>
    </Dialog>
  )
}
