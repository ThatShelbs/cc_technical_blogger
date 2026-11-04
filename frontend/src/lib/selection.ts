export type Located = { ok: true; source: string } | { ok: false; reason: string }

/** Markdown syntax that can sit between two words the reader sees as neighbours: emphasis, code ticks, link wrappers, list and quote marks. */
const BETWEEN = String.raw`(?:\s|[*_\x60>#\[-]|\]\([^)\s]*\))+`

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Map text selected in the rendered article back to the exact slice of the post's Markdown, so a rewrite
 * replaces the right characters even when the selection crosses bold, links or list items.
 */
export function locateInSource(markdown: string, selected: string): Located {
  const words = selected.trim().split(/\s+/).filter(Boolean)
  if (!words.length) return { ok: false, reason: 'Select some text first.' }

  const pattern = new RegExp(words.map(escapeRegExp).join(BETWEEN), 'g')
  const matches = [...markdown.matchAll(pattern)]
  if (!matches.length) {
    return { ok: false, reason: 'Could not match that selection to the text. Select inside one section, or use Edit Markdown.' }
  }
  if (matches.length > 1) {
    return { ok: false, reason: 'That wording appears more than once. Select a longer passage.' }
  }

  let start = matches[0].index ?? 0
  let end = start + matches[0][0].length
  // Take emphasis, code and link wrappers that open or close right at the edges, so the replacement stays balanced.
  const before = /(?:\*\*|\*|__|_|\x60|\[)+$/.exec(markdown.slice(0, start))
  if (before) start -= before[0].length
  const after = /^(?:\*\*|\*|__|_|\x60|\]\([^)\s]*\))+/.exec(markdown.slice(end))
  if (after) end += after[0].length
  return { ok: true, source: markdown.slice(start, end) }
}
