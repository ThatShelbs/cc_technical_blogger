import { useEffect, useRef } from 'react'

export interface KeyLike {
  key: string
  ctrlKey: boolean
  metaKey: boolean
  shiftKey: boolean
  altKey: boolean
}

/**
 * True when a key event matches a combo such as `mod+k`, `mod+enter` or `?`.
 * `mod` is Ctrl or Cmd, so one combo works on every platform.
 */
export function matchHotkey(event: KeyLike, combo: string): boolean {
  const parts = combo.toLowerCase().split('+')
  const key = parts[parts.length - 1]
  const wantsMod = parts.includes('mod')
  const wantsShift = parts.includes('shift')
  const wantsAlt = parts.includes('alt')
  const hasMod = event.ctrlKey || event.metaKey
  if (wantsMod !== hasMod || wantsAlt !== event.altKey) return false
  // A bare symbol such as "?" already encodes Shift, so only check Shift for letters and named keys.
  if (key.length > 1 || /[a-z0-9]/.test(key)) {
    if (wantsShift !== event.shiftKey) return false
  }
  return event.key.toLowerCase() === key
}

/** True when the event target is somewhere the user types (a bare-key shortcut must not fire there). */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
}

/**
 * Run `handler` on a hotkey. Combos with `mod` work everywhere (even inside a text box, which is what
 * Ctrl+S and Ctrl+Enter are for); bare keys such as `?` are ignored while typing.
 */
export function useHotkey(combo: string, handler: (event: KeyboardEvent) => void, enabled = true) {
  const latest = useRef(handler)
  useEffect(() => {
    latest.current = handler
  })
  useEffect(() => {
    if (!enabled) return
    const listener = (event: KeyboardEvent) => {
      if (!matchHotkey(event, combo)) return
      if (!combo.toLowerCase().includes('mod') && isTypingTarget(event.target)) return
      latest.current(event)
    }
    document.addEventListener('keydown', listener)
    return () => document.removeEventListener('keydown', listener)
  }, [combo, enabled])
}
