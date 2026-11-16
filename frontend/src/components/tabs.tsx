import { useRef, type KeyboardEvent, type ReactNode } from 'react'

import { cx } from '../lib/cx'
import { nextTabIndex, panelDomId, tabDomId } from '../lib/tabs'

export interface TabItem<T extends string> {
  id: T
  label: ReactNode
  icon?: ReactNode
}

/**
 * Accessible tab list: roving tabindex, arrow/Home/End keys, `aria-controls` to a panel rendered with
 * `panelDomId(idPrefix, value)`. Two looks: `underline` (page sections) and `segmented` (compact switch).
 */
export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  label,
  idPrefix,
  variant = 'underline',
  className,
}: {
  tabs: readonly TabItem<T>[]
  value: T
  onChange: (id: T) => void
  label: string
  idPrefix: string
  variant?: 'underline' | 'segmented'
  className?: string
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({})
  const onKeyDown = (event: KeyboardEvent) => {
    const current = tabs.findIndex((t) => t.id === value)
    const next = nextTabIndex(event.key, current, tabs.length)
    if (next === null) return
    event.preventDefault()
    const target = tabs[next]
    onChange(target.id)
    refs.current[target.id]?.focus()
  }
  return (
    <div
      role="tablist"
      aria-label={label}
      onKeyDown={onKeyDown}
      className={cx(
        variant === 'underline'
          ? 'flex gap-1 overflow-x-auto overflow-y-hidden border-b border-line'
          : 'inline-flex rounded-lg border border-line bg-surface p-1',
        className,
      )}
    >
      {tabs.map((tab) => {
        const selected = tab.id === value
        return (
          <button
            key={tab.id}
            ref={(el) => {
              refs.current[tab.id] = el
            }}
            type="button"
            role="tab"
            id={tabDomId(idPrefix, tab.id)}
            aria-selected={selected}
            aria-controls={panelDomId(idPrefix, tab.id)}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(tab.id)}
            className={cx(
              'inline-flex items-center gap-1.5 text-sm font-semibold whitespace-nowrap',
              variant === 'underline'
                ? cx('-mb-px border-b-2 px-4 py-2.5', selected ? 'border-accent text-fg' : 'border-transparent text-muted hover:text-fg')
                : cx('rounded-md px-3 py-1.5', selected ? 'bg-accent-soft' : 'text-muted hover:text-fg'),
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
