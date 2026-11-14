import type { JobState } from '../api/useJob'

export interface TextSyncNote {
  tone: 'success' | 'warn'
  text: string
}

/** What a finished image job did to the text around the image: a note to show, or null when it changed nothing. */
export function textSyncNote(state: Pick<JobState, 'result'>): TextSyncNote | null {
  const result = state.result ?? {}
  if (result.text_error) return { tone: 'warn', text: String(result.text_error) }
  if (Number(result.text_edits ?? 0) > 0) {
    const summary = String(result.text_summary ?? '').trim()
    return { tone: 'success', text: `${summary || 'The text around it was updated to match.'} Not right? Use “Undo last change”.` }
  }
  return null
}
