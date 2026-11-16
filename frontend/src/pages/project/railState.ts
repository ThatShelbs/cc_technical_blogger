const KEY_PREFIX = 'inferno-ghostwriter-rail-'

/** Saved open/closed state; storage can be blocked, so every access is guarded. */
export function readOpen(id: string, fallback: boolean): boolean {
  try {
    const saved = localStorage.getItem(KEY_PREFIX + id)
    return saved === null ? fallback : saved === '1'
  } catch {
    return fallback
  }
}

export function writeOpen(id: string, open: boolean) {
  try {
    localStorage.setItem(KEY_PREFIX + id, open ? '1' : '0')
  } catch {
    // Not remembering is fine.
  }
}
