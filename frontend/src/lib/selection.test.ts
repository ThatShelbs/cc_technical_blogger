import { describe, expect, it } from 'vitest'

import { locateInSource } from './selection'

const POST = `# Title

Bar charts win. **Every** single time, see [the guide](https://example.com/guide) for why.

{{image:img2}}

- First point about pies
- Second point about bars

Pies are fine. Pies are fine.
`

describe('locateInSource', () => {
  it('returns plain text as written', () => {
    expect(locateInSource(POST, 'Bar charts win.')).toEqual({ ok: true, source: 'Bar charts win.' })
  })

  it('maps text selected across bold and a link back to the Markdown, with balanced wrappers', () => {
    const located = locateInSource(POST, 'Every single time, see the guide')
    expect(located).toEqual({ ok: true, source: '**Every** single time, see [the guide](https://example.com/guide)' })
  })

  it('pulls in a wrapper that opens or closes right at the edge', () => {
    expect(locateInSource(POST, 'Every')).toEqual({ ok: true, source: '**Every**' })
  })

  it('works across list items', () => {
    const located = locateInSource(POST, 'about pies Second point')
    expect(located.ok && located.source).toBe('about pies\n- Second point')
  })

  it('refuses a selection that would span an image', () => {
    expect(locateInSource(POST, 'for why. Pies are fine.').ok).toBe(false)
  })

  it('asks for a longer selection when the wording repeats', () => {
    const located = locateInSource(POST, 'Pies are fine.')
    expect(located.ok).toBe(false)
  })

  it('rejects empty and unknown selections', () => {
    expect(locateInSource(POST, '   ').ok).toBe(false)
    expect(locateInSource(POST, 'not in the post').ok).toBe(false)
  })
})
