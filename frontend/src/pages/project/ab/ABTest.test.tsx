import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ABTestOut } from '../../../api/types.gen'
import { initialJobState, reduceJob } from '../../../api/useJob'
import { ABCompare } from './ABCompare'
import { AdoptDialog } from './ABReveal'

const post = (side: 'left' | 'right', title: string) => ({
  side,
  title,
  subtitle: '',
  markdown: `# ${title}\n\n*A subtitle.*\n\nSome text for ${title}.\n`,
  word_count: 812,
  status: 'ready',
  error: null,
  images: [],
})

const VOTING = {
  id: 3,
  project_id: 7,
  persona_id: 1,
  status: 'voting',
  error: null,
  left: post('left', 'Pies Are Lame'),
  right: post('right', 'Bars Win'),
  winner: null,
  winner_side: null,
  taken: [],
  tweaks: [],
  adopted: null,
  evolution_id: null,
  created_at: '2026-11-13T00:00:00Z',
  decided_at: null,
} as unknown as ABTestOut

const DECIDED = {
  ...VOTING,
  status: 'decided',
  left: null,
  right: null,
  winner: 'challenger',
  winner_side: 'right',
  taken: ['opener'],
  tweaks: [
    { id: 't1', group: 'Settings', label: 'Humor', before: '5/10', after: '7/10', suggested: true },
    { id: 't2', group: 'Formula', label: 'Opener', before: 'Your usual', after: 'A cold open', suggested: false },
    { id: 't3', group: 'Voice', label: 'Lean into', before: 'As usual', after: 'Ends sections on a punch', suggested: true },
  ],
} as unknown as ABTestOut

class FakeEventSource {
  addEventListener() {}
  close() {}
}

beforeEach(() => vi.stubGlobal('EventSource', FakeEventSource))
afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const sent = (fetchMock: ReturnType<typeof vi.spyOn>, path: string) => {
  const call = fetchMock.mock.calls.find(([url, init]: [unknown, RequestInit | undefined]) => url === path && init?.method === 'POST')
  return call?.[1]?.body ? JSON.parse(String(call[1].body)) : undefined
}

describe('reduceJob lanes', () => {
  it('keeps each post of an A/B test in its own lane', () => {
    let state = reduceJob(initialJobState, { type: 'lane', data: { lane: 'left', type: 'draft_delta', data: { text: '# One' } } })
    state = reduceJob(state, { type: 'lane', data: { lane: 'right', type: 'progress', data: { progress: 0.4, message: 'Drafting' } } })
    state = reduceJob(state, { type: 'lane', data: { lane: 'left', type: 'draft_delta', data: { text: ' more' } } })
    state = reduceJob(state, { type: 'lane', data: { lane: 'middle', type: 'draft_delta', data: { text: 'x' } } })
    expect(state.lanes.left?.draft).toBe('# One more')
    expect(state.lanes.right?.progress).toBe(0.4)
    expect(state.lanes.right?.message).toBe('Drafting')
    expect(state.draft).toBe('')
  })
})

describe('ABCompare', () => {
  it('shows both posts by position only and sends the pick with the parts to take', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      if (String(input) === '/api/ab-tests/3') return new Response(JSON.stringify(VOTING))
      return new Response(JSON.stringify({ id: 'job2', kind: 'ab_decide', status: 'queued' }), { status: 202 })
    })
    const onStarted = vi.fn()
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ABCompare projectId={7} testId={3} onStarted={onStarted} />
      </QueryClientProvider>,
    )

    const second = await screen.findByLabelText('Post 2')
    expect(within(second).getByRole('heading', { name: 'Bars Win' })).toBeInTheDocument()
    expect(screen.queryByText(/control|challenger|tweaked/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Pick a winner' })).toBeDisabled()

    await userEvent.click(within(second).getByRole('button', { name: 'Pick Post 2' }))
    expect(screen.getByRole('heading', { name: /Post 2 wins. Anything to take from Post 1/ })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('checkbox', { name: /Opener/ }))
    await userEvent.click(screen.getByRole('checkbox', { name: /Closing meme/ }))
    await userEvent.type(screen.getByLabelText(/Anything else to blend/), 'Keep the pun')
    await userEvent.click(screen.getByRole('button', { name: 'Keep Post 2 with the blend' }))

    await waitFor(() => expect(onStarted).toHaveBeenCalled())
    expect(sent(fetchMock, '/api/ab-tests/3/decide')).toEqual({ winner: 'right', take: ['opener', 'meme'], notes: 'Keep the pun' })
  })
})

describe('AdoptDialog', () => {
  it('pre-ticks what was in the kept post and adopts the chosen tweaks', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(async () => new Response(JSON.stringify({ ab_test: { ...DECIDED, adopted: ['t1', 't2', 't3'] }, job: null })))
    const onClose = vi.fn()
    render(
      <QueryClientProvider client={new QueryClient()}>
        <AdoptDialog test={DECIDED} projectId={7} onClose={onClose} />
      </QueryClientProvider>,
    )

    expect(screen.getByRole('checkbox', { name: /Humor/ })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: /Opener/ })).not.toBeChecked()
    expect(screen.getByRole('button', { name: 'Adopt 2 changes (new voice profile version)' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('checkbox', { name: /Opener/ }))
    await userEvent.click(screen.getByRole('button', { name: /Adopt 3 changes/ }))

    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(sent(fetchMock, '/api/ab-tests/3/adopt')).toEqual({ tweak_ids: ['t1', 't3', 't2'] })
  })
})
