import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { OpeningInfoOut, OpeningPitchOut, OpeningStyleOut } from '../../api/types.gen'
import { buildDials, dialsToState, emptyDials } from '../dials'
import { openingHint, rankPitches } from '../../lib/opening'
import { OpeningIdeasDialog } from './OpeningDialogs'

function pitch(index: number, style: string, label: string, total: number, extra: Partial<OpeningPitchOut> = {}): OpeningPitchOut {
  const each = Math.round(total / 4)
  return {
    index,
    style,
    style_label: label,
    template: '',
    hook: `Hook ${index}`,
    concept: `Concept ${index}`,
    scores: { scroller: each, art_director: each, fact_checker: each, author: each },
    note: `Note ${index}`,
    total,
    ruled_out: false,
    tried: false,
    current: false,
    ...extra,
  }
}

const OPENING: OpeningInfoOut = {
  style: 'editorial',
  style_label: 'Visual metaphor',
  template: '',
  mode: 'auto',
  summary: 'The plinko board says it fastest.',
  ideas_left: 1,
  fallback_from: '',
  pitches: [
    pitch(0, 'cheat_sheet', 'Cheat sheet', 28, { tried: true }),
    pitch(1, 'editorial', 'Visual metaphor', 34, { current: true, tried: true }),
    pitch(2, 'data_chart', 'Data story chart', 36, { ruled_out: true }),
    pitch(3, 'data_art', 'Data art', 30),
  ],
  sources: [],
  review: { verdict: 'passed', clickability: 8, craft: 8, problems: [], note: '' },
  slots: [],
  thumbnail_fit: 'cover',
}

const STYLES: OpeningStyleOut[] = [
  { id: 'editorial', label: 'Visual metaphor', summary: '', when_to_use: '', needs_data: false, min_humor: 0 },
  { id: 'data_art', label: 'Data art', summary: '', when_to_use: '', needs_data: false, min_humor: 0 },
  { id: 'cheat_sheet', label: 'Cheat sheet', summary: '', when_to_use: '', needs_data: false, min_humor: 0 },
  { id: 'framework', label: 'Framework diagram', summary: '', when_to_use: '', needs_data: false, min_humor: 0 },
]

describe('OpeningIdeasDialog', () => {
  it('ranks the pitches as the panel did and lets the author build one, ask for the next, or try a style', async () => {
    const onPick = vi.fn()
    const onNext = vi.fn()
    const onStyle = vi.fn()
    render(<OpeningIdeasDialog open onClose={vi.fn()} opening={OPENING} styles={STYLES} onPick={onPick} onNext={onNext} onStyle={onStyle} />)

    const items = screen.getAllByRole('listitem')
    // The ruled-out chart scored highest but ranks last; the metaphor is the panel's pick.
    expect(items.map((li) => li.getAttribute('aria-label'))).toEqual([
      'Visual metaphor: Concept 1',
      'Data art: Concept 3',
      'Cheat sheet: Concept 0',
      'Data story chart: Concept 2',
    ])
    expect(within(items[0]).getByText('Panel pick')).toBeInTheDocument()
    expect(within(items[0]).getByText('Showing now')).toBeInTheDocument()
    expect(within(items[3]).getByText('Ruled out')).toBeInTheDocument()
    expect(within(items[1]).getByText('30/40')).toBeInTheDocument()
    expect(screen.getByText('Panel: The plinko board says it fastest.')).toBeInTheDocument()

    await userEvent.click(within(items[1]).getByRole('button', { name: 'Use this one' }))
    expect(onPick).toHaveBeenCalledWith(3)
    await userEvent.click(screen.getByRole('button', { name: 'Next best idea' }))
    expect(onNext).toHaveBeenCalled()
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Pitch new ideas in one style' }), 'framework')
    expect(onStyle).toHaveBeenCalledWith('framework')
  })
})

describe('opening helpers', () => {
  it('describes what Auto will weigh', () => {
    expect(openingHint(['cheat_sheet', 'framework', 'editorial', 'data_art'], STYLES)).toBe(
      'Pitches ideas across Cheat sheet and Framework diagram, plus open visual metaphors and data art; four judges score every idea and the best one is drawn.',
    )
    expect(openingHint(['editorial', 'data_art'], STYLES)).toMatch(/^Pitches open visual metaphors/)
  })

  it('ranks usable pitches by total and ruled-out ones last', () => {
    expect(rankPitches(OPENING.pitches).map((p) => p.index)).toEqual([1, 3, 0, 2])
  })

  it('round-trips the opening style and note through the dials', () => {
    const dials = { opening_style: 'big_number', opening_note: 'Lead with the 62%' }
    expect(buildDials(dialsToState(dials))).toEqual(dials)
    expect(buildDials({ ...emptyDials, openingNote: '  ' })).toEqual({})
  })
})
