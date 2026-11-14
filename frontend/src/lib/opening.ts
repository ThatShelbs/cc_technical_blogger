import type { OpeningPitchOut, OpeningStyleOut } from '../api/types.gen'

/** The open styles every Auto round includes, whatever the article type. */
export const OPEN_STYLES = ['editorial', 'data_art']

export const JUDGES: { key: string; label: string; hint: string }[] = [
  { key: 'scroller', label: 'Scroller', hint: 'Would a reader in a busy feed stop and click?' },
  { key: 'art_director', label: 'Art director', hint: 'Crisp, professional, clearly designed by a person' },
  { key: 'fact_checker', label: 'Fact checker', hint: 'Accurate, specific and, for data, sourceable' },
  { key: 'author', label: 'Author', hint: 'Relevant to the title and the post, in your voice' },
]

/** What Auto will weigh, in words: "Pitches across Cheat sheet and Framework diagram, plus open visual metaphors and data art." */
export function openingHint(suits: string[], styles: OpeningStyleOut[]): string {
  const label = (id: string) => styles.find((s) => s.id === id)?.label ?? id
  const fits = suits.filter((s) => !OPEN_STYLES.includes(s)).map(label)
  const lead = fits.length ? `Pitches ideas across ${listJoin(fits)}, plus` : 'Pitches'
  return `${lead} open visual metaphors and data art; four judges score every idea and the best one is drawn.`
}

export function listJoin(items: string[]): string {
  if (items.length <= 1) return items.join('')
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
}

/** The pitches best first, as the panel ranked them: usable ones by total, ruled-out ones last. */
export function rankPitches(pitches: OpeningPitchOut[]): OpeningPitchOut[] {
  return [...pitches].sort((a, b) => Number(a.ruled_out) - Number(b.ruled_out) || b.total - a.total || b.scores.scroller - a.scores.scroller)
}
