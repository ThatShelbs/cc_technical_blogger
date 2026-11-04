import type { ReferenceOut, ReferenceRedrawIn } from '../api/types.gen'

export type ReferenceKind = NonNullable<ReferenceRedrawIn['kind']>

export const REFERENCE_KINDS: { kind: ReferenceKind; label: string; hint: string }[] = [
  { kind: 'source', label: 'Source', hint: 'Evidence for a claim: a paper, docs, a report' },
  { kind: 'quote', label: 'Quote', hint: 'A famous quote, credited to who said it' },
  { kind: 'social_post', label: 'Social post', hint: 'A widely shared post from an AI/ML voice' },
  { kind: 'resource', label: 'Resource', hint: 'A tutorial, Python package or video' },
  { kind: 'related_article', label: 'Related article', hint: 'A closely related article or post' },
]

export const kindLabel = (kind: string) => REFERENCE_KINDS.find((k) => k.kind === kind)?.label ?? kind

/** Placements a kind can take; a reference in the "Go deeper" list can only become another list item. */
export function kindsFor(ref: ReferenceOut): ReferenceKind[] {
  const listable: ReferenceKind[] = ['resource', 'related_article']
  return ref.placement === 'go_deeper' ? listable : REFERENCE_KINDS.map((k) => k.kind)
}

/** The site a link points to, for a compact label ("arxiv.org"). */
export function domain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

/** Mirrors the backend: at least five, one more per 500 words past 2,000, at most twelve. */
export function autoReferenceCount(targetWords: number): number {
  return Math.max(5, Math.min(12, 5 + Math.floor((targetWords - 2000) / 500)))
}

/** The reference a link in the post belongs to, matched by URL. */
export function referenceForHref(references: ReferenceOut[], href: string | undefined): ReferenceOut | undefined {
  if (!href) return undefined
  return references.find((r) => r.status === 'ready' && r.in_post && r.url === href)
}
