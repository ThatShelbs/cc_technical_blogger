import type { ImageOut } from '../api/types.gen'

export type ArticlePart = { type: 'text'; text: string } | { type: 'image'; slot: string }

const PLACEHOLDER = /^[ \t]*\{\{image:([A-Za-z0-9_-]+)\}\}[ \t]*$/gm

/** Split post Markdown into text chunks and image slots, in order. */
export function splitArticle(markdown: string): ArticlePart[] {
  const parts: ArticlePart[] = []
  let last = 0
  for (const match of markdown.matchAll(PLACEHOLDER)) {
    const index = match.index ?? 0
    if (index > last) parts.push({ type: 'text', text: markdown.slice(last, index) })
    parts.push({ type: 'image', slot: match[1] })
    last = index + match[0].length
  }
  if (last < markdown.length) parts.push({ type: 'text', text: markdown.slice(last) })
  return parts.filter((p) => p.type === 'image' || p.text.trim())
}

/** Pull "# Title" and an italic subtitle line off the top of the post. */
export function splitHeader(markdown: string): { title: string; subtitle: string; body: string } {
  const lines = markdown.replace(/^\s+/, '').split('\n')
  let title = ''
  let subtitle = ''
  let i = 0
  if (lines[0]?.startsWith('# ')) {
    title = lines[0].slice(2).trim()
    i = 1
    while (i < lines.length && !lines[i].trim()) i++
    const candidate = lines[i]?.trim() ?? ''
    if (/^\*[^*].*\*$/.test(candidate) || /^_[^_].*_$/.test(candidate)) {
      subtitle = candidate.slice(1, -1).trim()
      i++
    }
  }
  return { title, subtitle, body: lines.slice(i).join('\n') }
}

export function fullCaption(image: Pick<ImageOut, 'caption' | 'credit'>): string {
  const caption = image.caption.trim()
  const credit = image.credit.trim()
  if (!credit || caption.toLowerCase().includes(credit.toLowerCase())) return caption
  if (!caption) return credit
  return `${caption}${/[.!?;]$/.test(caption) ? ' ' : '; '}${credit}`
}
