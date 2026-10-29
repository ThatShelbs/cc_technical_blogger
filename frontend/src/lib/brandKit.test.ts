import { describe, expect, it } from 'vitest'

import { brandKitOf, emptyBrandKit, isEmptyBrandKit } from './brandKit'

describe('brand kit helpers', () => {
  it('fills missing fields and copies the palette', () => {
    const saved = { palette: ['#112233'] }
    const kit = brandKitOf(saved)
    expect(kit).toEqual({ ...emptyBrandKit, palette: ['#112233'] })
    kit.palette.push('#445566')
    expect(saved.palette).toEqual(['#112233'])
    expect(brandKitOf(null)).toEqual(emptyBrandKit)
  })

  it('treats whitespace-only fields as empty', () => {
    expect(isEmptyBrandKit({ style: '  ', font: '', motif: ' ', palette: [] })).toBe(true)
    expect(isEmptyBrandKit({ motif: 'a tiny robot' })).toBe(false)
    expect(isEmptyBrandKit({ palette: ['#000004'] })).toBe(false)
  })
})
