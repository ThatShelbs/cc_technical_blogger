import { useEffect, type RefObject } from 'react'

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/** The element Tab should land on when leaving `from` in a loop of `items` (null: let the browser decide). */
export function trapTarget<T>(items: T[], from: T | null, backwards: boolean): T | null {
  if (!items.length) return null
  const first = items[0]
  const last = items[items.length - 1]
  if (backwards && (from === first || from === null || !items.includes(from))) return last
  if (!backwards && (from === last || !items.includes(from as T))) return first
  return null
}

/**
 * While `active`: move focus into `container`, keep Tab inside it, close on Escape, and give focus back
 * to whatever had it before when it ends.
 */
export function useFocusTrap(container: RefObject<HTMLElement | null>, active: boolean, onEscape: () => void) {
  useEffect(() => {
    const root = container.current
    if (!active || !root) return
    const previous = document.activeElement as HTMLElement | null
    const items = () => Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE))
    items()[0]?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        onEscape()
        return
      }
      if (event.key !== 'Tab') return
      const target = trapTarget(items(), document.activeElement as HTMLElement | null, event.shiftKey)
      if (target) {
        event.preventDefault()
        target.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      previous?.focus?.()
    }
    // onEscape is read at call time through the closure of the latest render; re-running on it would steal focus.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, container])
}
