import { describe, expect, it } from 'vitest'

import { planOutline } from '../lib/outline'
import { buildDials, dialsToState, emptyDials } from './dials'

describe('dialsToState', () => {
  it('round-trips through buildDials', () => {
    const dials = { target_words: 2200, humor: 3, education: 'expert', opinion: 8, topic: 'Machine Learning', audience: 'ML leads', platform: 'x' } as const
    expect(buildDials(dialsToState(dials))).toEqual(dials)
  })

  it('treats missing dials as persona defaults', () => {
    expect(dialsToState(null)).toEqual(emptyDials)
    expect(buildDials({ ...emptyDials, audience: '   ' })).toEqual({})
  })
})

describe('planOutline', () => {
  it('turns the plan into an editable bullet outline', () => {
    const plan = {
      chosen_title: 'Pie Charts Are Lame',
      hook: 'Admit to hating pie charts.',
      sections: [
        { heading: 'Why People Love Pies', key_points: ['they look friendly'] },
        { heading: 'What To Use Instead', key_points: [] },
      ],
      closing: 'Reach for a bar.',
    }
    expect(planOutline(plan)).toBe(
      'Pie Charts Are Lame\n- opening: Admit to hating pie charts.\n- Why People Love Pies\n  - they look friendly\n- What To Use Instead\n- close: Reach for a bar.',
    )
    expect(planOutline(null)).toBe('')
  })
})
