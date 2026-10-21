import { describe, expect, it } from 'vitest'

import { initialJobState, reduceJob } from './useJob'

describe('reduceJob', () => {
  it('streams draft text, resets on revision, and finishes', () => {
    let state = reduceJob(initialJobState, { type: 'progress', data: { progress: 0.2, message: 'Writing' } })
    state = reduceJob(state, { type: 'draft_delta', data: { text: '# Hello' } })
    state = reduceJob(state, { type: 'draft_delta', data: { text: ' world' } })
    expect(state.draft).toBe('# Hello world')
    expect(state.status).toBe('running')
    expect(state.message).toBe('Writing')

    state = reduceJob(state, { type: 'draft_reset', data: {} })
    expect(state.draft).toBe('')

    state = reduceJob(state, { type: 'status', data: { status: 'succeeded', error: null } })
    expect(state.status).toBe('succeeded')
    expect(state.progress).toBe(1)
  })

  it('records failures, critiques and finished images', () => {
    let state = reduceJob(initialJobState, { type: 'critique', data: { voice: 7, overall: 8 } })
    state = reduceJob(state, { type: 'image_ready', data: { image_id: 4 } })
    state = reduceJob(state, { type: 'status', data: { status: 'failed', error: 'Rate limited' } })
    expect(state.critique?.voice).toBe(7)
    expect(state.imagesReady).toEqual([4])
    expect(state.status).toBe('failed')
    expect(state.error).toBe('Rate limited')
  })

  it('ignores unknown events', () => {
    expect(reduceJob(initialJobState, { type: 'mystery', data: {} })).toBe(initialJobState)
  })
})
