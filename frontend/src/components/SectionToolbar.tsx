import { ImagePlus, Link2, Maximize2, MessageSquareText, Minimize2, Quote, Wand2 } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode, type RefObject } from 'react'

import type { RewriteIn } from '../api/types.gen'
import { locateInSource } from '../lib/selection'
import { Button, Textarea } from './ui'

export type SectionAction = NonNullable<RewriteIn['action']>

const ACTIONS: { action: Exclude<SectionAction, 'custom'>; label: string; icon: ReactNode; hint: string }[] = [
  { action: 'rewrite', label: 'Rewrite', icon: <Wand2 className="size-4" />, hint: 'Same point, fresh phrasing' },
  { action: 'compact', label: 'Compact', icon: <Minimize2 className="size-4" />, hint: 'Tighter, about half the length' },
  { action: 'expand', label: 'Expand', icon: <Maximize2 className="size-4" />, hint: 'Add depth and an example' },
  { action: 'add_source', label: 'Add source', icon: <Link2 className="size-4" />, hint: 'Find and cite a real source (web search)' },
  { action: 'add_quote', label: 'Add quote', icon: <Quote className="size-4" />, hint: 'Find a famous, attributed quote (web search)' },
]

const PENDING_TEXT: Record<SectionAction, string> = {
  custom: 'Rewriting in your voice…',
  rewrite: 'Rewriting in your voice…',
  compact: 'Tightening it…',
  expand: 'Expanding it…',
  add_source: 'Searching the web for a source…',
  add_quote: 'Searching the web for a quote…',
}

export interface SectionRun {
  action: SectionAction
  instruction: string
}

/** The six ways to regenerate a highlighted section; "Custom brief" takes feedback such as "make it more positive". */
export function SectionActions({
  onRun,
  onAddImage,
  pending,
  disabled,
}: {
  onRun: (run: SectionRun) => void
  /** Draw an image near the highlight (the page finds the nearest paragraph or sentence break). */
  onAddImage?: () => void
  pending: SectionAction | null
  disabled?: boolean
}) {
  const [custom, setCustom] = useState(false)
  const [brief, setBrief] = useState('')
  const locked = disabled || pending !== null

  if (pending) {
    return (
      <p role="status" className="px-2 py-1 text-sm font-semibold">
        {PENDING_TEXT[pending]}
      </p>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1" role="group" aria-label="Regenerate the highlighted section">
        {ACTIONS.map(({ action, label, icon, hint }) => (
          <Button key={action} size="sm" variant="ghost" icon={icon} title={hint} disabled={locked} onClick={() => onRun({ action, instruction: '' })}>
            {label}
          </Button>
        ))}
        {onAddImage && (
          <Button
            size="sm"
            variant="ghost"
            icon={<ImagePlus className="size-4" />}
            title="Draw a relevant image after this passage and adjust nearby text if needed"
            disabled={locked}
            onClick={onAddImage}
          >
            Add image
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          icon={<MessageSquareText className="size-4" />}
          title="Describe how it should change"
          aria-expanded={custom}
          disabled={locked}
          onClick={() => setCustom((open) => !open)}
        >
          Custom brief
        </Button>
      </div>
      {custom && (
        <form
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (brief.trim()) onRun({ action: 'custom', instruction: brief.trim() })
          }}
        >
          <Textarea
            rows={2}
            value={brief}
            maxLength={4000}
            autoFocus
            onChange={(e) => setBrief(e.target.value)}
            aria-label="How should this section change?"
            placeholder="Make it more positive, add an analogy, explain it for beginners…"
          />
          <Button type="submit" size="sm" icon={<Wand2 className="size-4" />} disabled={locked || !brief.trim()}>
            Apply brief
          </Button>
        </form>
      )}
    </div>
  )
}

interface Captured {
  source: string
  top: number
  left: number
}

/**
 * Floating toolbar for text highlighted in the rendered article. It maps the highlight back to the post's
 * Markdown and hands that exact slice to `onRun`.
 */
export function SectionToolbar({
  container,
  markdown,
  pending,
  disabled,
  onRun,
  onAddImage,
}: {
  container: RefObject<HTMLElement | null>
  markdown: string
  pending: SectionAction | null
  disabled?: boolean
  onRun: (source: string, run: SectionRun) => void
  onAddImage?: (source: string) => void
}) {
  const [captured, setCaptured] = useState<Captured | null>(null)
  const [problem, setProblem] = useState('')
  const bar = useRef<HTMLDivElement>(null)

  // A new post text (after a rewrite or undo) makes the captured slice stale.
  const [seenMarkdown, setSeenMarkdown] = useState(markdown)
  if (seenMarkdown !== markdown) {
    setSeenMarkdown(markdown)
    setCaptured(null)
    setProblem('')
  }

  useEffect(() => {
    const onSelection = () => {
      const root = container.current
      const sel = window.getSelection()
      if (!root || !sel || sel.isCollapsed || !sel.rangeCount) return
      const range = sel.getRangeAt(0)
      if (!root.contains(range.commonAncestorContainer) || bar.current?.contains(range.commonAncestorContainer)) return
      const text = sel.toString()
      if (!text.trim()) return
      const rect = range.getBoundingClientRect()
      const box = root.getBoundingClientRect()
      const top = Math.max(0, rect.top - box.top - 8)
      const left = Math.max(0, Math.min(rect.left - box.left, box.width - 280))
      const located = locateInSource(markdown, text)
      if (located.ok) {
        setProblem('')
        setCaptured({ source: located.source, top, left })
      } else {
        setCaptured({ source: '', top, left })
        setProblem(located.reason)
      }
    }
    const onDown = (e: MouseEvent) => {
      if (bar.current?.contains(e.target as Node)) return
      setCaptured(null)
      setProblem('')
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setCaptured(null)
    }
    document.addEventListener('selectionchange', onSelection)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('selectionchange', onSelection)
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [container, markdown])

  if (!captured) return null
  return (
    <div
      ref={bar}
      role="toolbar"
      aria-label="Section actions"
      className="absolute z-20 w-[min(34rem,calc(100%-1rem))] -translate-y-full rounded-xl border border-line bg-surface p-2 shadow-lg"
      style={{ top: captured.top, left: captured.left }}
      // Keep the highlight while a button is pressed; the brief box still takes focus normally.
      onMouseDown={(e) => {
        if (!(e.target instanceof HTMLTextAreaElement)) e.preventDefault()
      }}
    >
      {problem ? (
        <p className="px-2 py-1 text-sm text-muted">{problem}</p>
      ) : (
        <SectionActions
          pending={pending}
          disabled={disabled}
          onRun={(run) => onRun(captured.source, run)}
          onAddImage={onAddImage && (() => onAddImage(captured.source))}
        />
      )}
    </div>
  )
}
