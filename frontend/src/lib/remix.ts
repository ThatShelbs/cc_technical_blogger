import type { ImageOut, RemixOut } from '../api/types.gen'

const DIMENSION_LABEL: Record<string, string> = { palette: 'colors', cast: 'cast', staging: 'staging', medium: 'medium' }

/** What the last redraw experimented with, e.g. "colors: Viridis, cast: Dogs" ("" when nothing was). */
export function remixTwists(remix: RemixOut | null | undefined): string {
  return (remix?.tweaks ?? []).map((t) => `${DIMENSION_LABEL[t.dimension] ?? t.dimension}: ${t.label}`).join(', ')
}

/** One line on the last redraw: what Claude set out to fix and the twist it tried ("" before the first redraw). */
export function remixSummary(remix: RemixOut | null | undefined): string {
  if (!remix) return ''
  const fix = remix.improvements[0] ?? remix.weakness
  const twists = remixTwists(remix)
  return [fix && `fixed "${fix.replace(/\.$/, '')}"`, twists && `tried ${twists}`].filter(Boolean).join('; ')
}

/** Earlier images this one could extend: drawn by Claude, not the opening image or the closing meme. */
export function buildOnChoices(image: ImageOut, images: ImageOut[]): ImageOut[] {
  if (image.kind === 'hero' || image.kind === 'meme') return []
  return images.filter(
    (other) => other.position < image.position && other.kind !== 'hero' && other.kind !== 'meme' && !['upload', 'placeholder', ''].includes(other.provider),
  )
}

/** Slot ids of the images that extend `image`, directly or through each other, in post order. */
export function dependentsOf(image: ImageOut, images: ImageOut[]): string[] {
  const reached = new Set([image.slot_id])
  const found: string[] = []
  for (const other of [...images].sort((a, b) => a.position - b.position)) {
    if (other.builds_on && reached.has(other.builds_on)) {
      reached.add(other.slot_id)
      found.push(other.slot_id)
    }
  }
  return found
}
