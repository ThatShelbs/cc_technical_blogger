import { describe, expect, it } from 'vitest'

import { textSyncNote } from './textSync'

describe('textSyncNote', () => {
  it('says nothing when the text was left alone', () => {
    expect(textSyncNote({ result: { image_id: 1, text_edits: 0, text_summary: '' } })).toBeNull()
    expect(textSyncNote({ result: null })).toBeNull()
  })

  it('reports what changed and how to undo it', () => {
    const note = textSyncNote({ result: { text_edits: 2, text_summary: 'Dropped the Drake line.' } })
    expect(note?.tone).toBe('success')
    expect(note?.text).toContain('Dropped the Drake line.')
    expect(note?.text).toContain('Undo last change')
  })

  it('warns, without failing, when the text could not be checked', () => {
    const note = textSyncNote({ result: { text_edits: 0, text_error: 'The image was redrawn, but the text could not be checked.' } })
    expect(note).toEqual({ tone: 'warn', text: 'The image was redrawn, but the text could not be checked.' })
  })
})
