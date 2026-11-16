import { ChevronDown } from 'lucide-react'
import { useId, useState, type ReactNode } from 'react'

import { cx } from '../../lib/cx'
import { readOpen, writeOpen } from './railState'

/** A titled, collapsible group of editor-rail cards that remembers whether it was open. */
export function RailGroup({
  id,
  title,
  hint,
  defaultOpen = false,
  children,
}: {
  id: string
  title: string
  hint?: string
  defaultOpen?: boolean
  children: ReactNode
}) {
  const [open, setOpen] = useState(() => readOpen(id, defaultOpen))
  const panelId = useId()
  return (
    <section aria-label={title}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => {
          writeOpen(id, !open)
          setOpen(!open)
        }}
        className="flex w-full items-center justify-between gap-2 rounded-xl border border-line bg-surface px-4 py-3 text-left hover:bg-surface-2"
      >
        <span className="min-w-0">
          <span className="block font-bold">{title}</span>
          {hint && <span className="block truncate text-xs text-muted">{hint}</span>}
        </span>
        <ChevronDown className={cx('size-4 shrink-0 text-muted transition', open && 'rotate-180')} aria-hidden />
      </button>
      <div id={panelId} hidden={!open} className="mt-3 space-y-4">
        {children}
      </div>
    </section>
  )
}
