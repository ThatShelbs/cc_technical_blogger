import { useEffect, useRef, useState } from 'react'

export type JobStatus = 'idle' | 'queued' | 'running' | 'succeeded' | 'failed'

export interface Critique {
  voice: number
  tone: number
  structure: number
  humor_match: number
  education_match: number
  skimmability: number
  image_placement: number
  overall: number
  strengths: string[]
  issues: string[]
  revision_instructions: string[]
}

export interface JobState {
  status: JobStatus
  progress: number
  message: string
  error: string | null
  /** Streamed post text (draft, then each revision). */
  draft: string
  /** Streamed voice-profile text. */
  voice: string
  plan: Record<string, unknown> | null
  critique: Critique | null
  imagesReady: number[]
  /** What the job returned, once it succeeded. */
  result: Record<string, unknown> | null
}

export const initialJobState: JobState = {
  status: 'idle',
  progress: 0,
  message: '',
  error: null,
  draft: '',
  voice: '',
  plan: null,
  critique: null,
  imagesReady: [],
  result: null,
}

interface JobEvent {
  type: string
  data: Record<string, unknown>
}

/** Apply one server event to the job state (pure, so it is easy to test). */
export function reduceJob(state: JobState, event: JobEvent): JobState {
  const { type, data } = event
  switch (type) {
    case 'progress':
      return { ...state, status: 'running', progress: Number(data.progress ?? state.progress), message: String(data.message ?? '') }
    case 'draft_delta':
      return { ...state, draft: state.draft + String(data.text ?? '') }
    case 'draft_reset':
      return { ...state, draft: '' }
    case 'voice_delta':
      return { ...state, voice: state.voice + String(data.text ?? '') }
    case 'plan':
      return { ...state, plan: data }
    case 'critique':
      return { ...state, critique: data as unknown as Critique }
    case 'image_ready':
      return { ...state, imagesReady: [...state.imagesReady, Number(data.image_id)] }
    case 'status': {
      const status = String(data.status) as JobStatus
      return {
        ...state,
        status,
        error: (data.error as string | null) ?? null,
        result: (data.result as Record<string, unknown> | null) ?? state.result,
        progress: status === 'succeeded' ? 1 : state.progress,
      }
    }
    default:
      return state
  }
}

const EVENT_TYPES = ['progress', 'draft_delta', 'draft_reset', 'voice_delta', 'plan', 'critique', 'image_ready', 'status']

/**
 * Follow a background job over Server-Sent Events. Events carry a sequence id, so a
 * reconnect that replays history is de-duplicated instead of doubling the draft text.
 */
export function useJob(jobId: string | null | undefined, onFinish?: (state: JobState) => void): JobState {
  // State is keyed by job id, so switching jobs starts from a clean "queued" state without a reset effect.
  const [entry, setEntry] = useState<{ id: string | null; state: JobState }>({ id: null, state: initialJobState })
  const finishRef = useRef(onFinish)
  useEffect(() => {
    finishRef.current = onFinish
  }, [onFinish])

  useEffect(() => {
    if (!jobId) return
    let lastSeq = -1
    let current: JobState = { ...initialJobState, status: 'queued' }
    const source = new EventSource(`/api/jobs/${jobId}/events`)

    const handle = (type: string) => (event: MessageEvent<string>) => {
      const seq = Number(event.lastEventId)
      if (!Number.isNaN(seq) && seq <= lastSeq) return
      lastSeq = Number.isNaN(seq) ? lastSeq : seq
      current = reduceJob(current, { type, data: JSON.parse(event.data) })
      setEntry({ id: jobId, state: current })
      if (type === 'status' && (current.status === 'succeeded' || current.status === 'failed')) {
        source.close()
        finishRef.current?.(current)
      }
    }
    EVENT_TYPES.forEach((type) => source.addEventListener(type, handle(type) as EventListener))
    return () => source.close()
  }, [jobId])

  if (!jobId) return initialJobState
  return entry.id === jobId ? entry.state : { ...initialJobState, status: 'queued' }
}
