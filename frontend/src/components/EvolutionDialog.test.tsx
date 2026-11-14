import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { EvolutionOut } from '../api/types.gen'
import { EvolutionDialog } from './EvolutionDialog'

const EVOLUTION = {
  id: 4,
  persona_id: 2,
  project_id: 9,
  kind: 'edits',
  state: 'pending',
  project_title: 'Pie Charts Are Lame',
  summary: 'You trimmed the throat-clearing.',
  items: [
    { id: 'c1', area: 'Voice & Tone', change: 'Open with the example.', evidence: 'Moved the example up.', target: 'profile', applied: false },
    { id: 'c2', area: 'Humor', change: 'End on an aside.', evidence: 'Added an aside.', target: 'playbook', applied: false },
  ],
} as unknown as EvolutionOut

/** jsdom has no EventSource; the job never reports back, which is all these tests need. */
class FakeEventSource {
  addEventListener() {}
  close() {}
}

beforeEach(() => vi.stubGlobal('EventSource', FakeEventSource))
afterEach(() => vi.unstubAllGlobals())

function setup(onClose = vi.fn()) {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
    if (String(url).endsWith('/apply')) return new Response(JSON.stringify({ id: 'job1', kind: 'apply_evolution', status: 'queued' }))
    return new Response(JSON.stringify({ ...EVOLUTION, state: 'dismissed' }))
  })
  render(
    <QueryClientProvider client={new QueryClient()}>
      <EvolutionDialog evolution={EVOLUTION} personaId={2} projectId={9} open onClose={onClose} />
    </QueryClientProvider>,
  )
  const body = (path: string) => {
    const call = fetchMock.mock.calls.find(([url, init]) => url === path && init?.method === 'POST')
    return call?.[1]?.body ? JSON.parse(String(call[1].body)) : call && {}
  }
  return { body, onClose }
}

describe('EvolutionDialog', () => {
  it('shows every suggestion ticked, with where it goes', () => {
    setup()
    expect(screen.getByText('You trimmed the throat-clearing.')).toBeInTheDocument()
    expect(screen.getAllByRole('checkbox').every((box) => (box as HTMLInputElement).checked)).toBe(true)
    expect(screen.getByText('Voice profile')).toBeInTheDocument()
    expect(screen.getByText('Playbook')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Apply 2 (new voice profile version)' })).toBeEnabled()
  })

  it('applies only the ticked suggestions', async () => {
    const { body } = setup()
    await userEvent.click(screen.getByRole('checkbox', { name: /Open with the example/ }))
    const apply = screen.getByRole('button', { name: 'Apply 1' })
    await userEvent.click(apply)
    await waitFor(() => expect(body('/api/evolutions/4/apply')).toEqual({ item_ids: ['c2'] }))
  })

  it('needs at least one suggestion', async () => {
    setup()
    for (const box of screen.getAllByRole('checkbox')) await userEvent.click(box)
    expect(screen.getByRole('button', { name: 'Apply 0' })).toBeDisabled()
  })

  it('dismisses the proposal', async () => {
    const { body, onClose } = setup()
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss all' }))
    await waitFor(() => expect(body('/api/evolutions/4/dismiss')).toBeTruthy())
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })
})
