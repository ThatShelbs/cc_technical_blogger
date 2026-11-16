export interface PaletteEntry {
  id: string
  label: string
  /** Group heading, e.g. "Go to", "Actions", "Posts". */
  group: string
  /** Extra words that should match but are not shown. */
  keywords?: string
}

/** Every query word must appear in the label, group or keywords (any order, case-insensitive). */
export function matchesQuery(entry: PaletteEntry, query: string): boolean {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  if (!words.length) return true
  const haystack = `${entry.label} ${entry.group} ${entry.keywords ?? ''}`.toLowerCase()
  return words.every((w) => haystack.includes(w))
}

/** Matching entries, label matches first, capped so a long post list stays usable. */
export function filterEntries(entries: PaletteEntry[], query: string, limit = 30): PaletteEntry[] {
  const q = query.trim().toLowerCase()
  const hits = entries.filter((e) => matchesQuery(e, q))
  if (!q) return hits.slice(0, limit)
  const rank = (e: PaletteEntry) => (e.label.toLowerCase().startsWith(q) ? 0 : e.label.toLowerCase().includes(q) ? 1 : 2)
  return [...hits].sort((a, b) => rank(a) - rank(b)).slice(0, limit)
}
