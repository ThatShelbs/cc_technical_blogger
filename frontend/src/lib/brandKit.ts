import type { BrandKit } from '../api/types.gen'

export const MAX_BRAND_COLORS = 8

export const emptyBrandKit: Required<BrandKit> = { style: '', palette: [], font: '', motif: '' }

export function brandKitOf(kit: BrandKit | null | undefined): Required<BrandKit> {
  return { ...emptyBrandKit, ...kit, palette: [...(kit?.palette ?? [])] }
}

export function isEmptyBrandKit(kit: BrandKit): boolean {
  return !kit.style?.trim() && !kit.font?.trim() && !kit.motif?.trim() && !kit.palette?.length
}
