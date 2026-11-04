import { describe, expect, it } from 'vitest'

import type { ReferenceOut } from '../api/types.gen'
import { autoReferenceCount, domain, kindsFor, referenceForHref } from './references'

function reference(extra: Partial<ReferenceOut> = {}): ReferenceOut {
  return {
    id: 1,
    slot_id: 'r1',
    position: 0,
    kind: 'source',
    placement: 'inline',
    purpose: '',
    url: 'https://www.example.com/paper',
    title: 'A paper',
    speaker: '',
    quote: '',
    status: 'ready',
    error: null,
    in_post: true,
    history: [],
    ...extra,
  }
}

describe('references', () => {
  it('matches the backend default count', () => {
    expect([800, 2000, 2500, 3000, 6000].map(autoReferenceCount)).toEqual([5, 5, 6, 7, 12])
  })

  it('finds the reference a link belongs to, only while it is in the post', () => {
    const refs = [reference(), reference({ id: 2, url: 'https://b.example', in_post: false })]
    expect(referenceForHref(refs, 'https://www.example.com/paper')?.id).toBe(1)
    expect(referenceForHref(refs, 'https://b.example')).toBeUndefined()
    expect(referenceForHref(refs, undefined)).toBeUndefined()
  })

  it('labels and limits kinds', () => {
    expect(domain('https://www.example.com/x')).toBe('example.com')
    expect(kindsFor(reference({ placement: 'go_deeper', kind: 'resource' }))).toEqual(['resource', 'related_article'])
    expect(kindsFor(reference())).toHaveLength(5)
  })
})
