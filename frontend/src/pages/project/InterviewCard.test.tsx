import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { ProjectOut } from '../../api/types.gen'
import { InterviewCard } from './InterviewCard'

const PROJECT = {
  id: 7,
  prompt: 'Why pie charts are lame',
  interview: [
    { question: 'Worst chart you ever defended?', answer: '' },
    { question: 'Who is this for?', answer: '' },
    { question: 'Your one rule?', answer: '' },
  ],
} as unknown as ProjectOut

function setup() {
  const fetchMock = vi
    .spyOn(globalThis, 'fetch')
    .mockImplementation(async () => new Response(JSON.stringify({ id: 'job1', kind: 'generate_post', status: 'queued' })))
  const onStarted = vi.fn()
  render(
    <QueryClientProvider client={new QueryClient()}>
      <InterviewCard project={PROJECT} onStarted={onStarted} />
    </QueryClientProvider>,
  )
  const sent = () => {
    const call = fetchMock.mock.calls.find(([url, init]) => url === '/api/projects/7/generate' && init?.method === 'POST')
    return call?.[1]?.body ? JSON.parse(String(call[1].body)) : undefined
  }
  return { sent, onStarted }
}

describe('InterviewCard', () => {
  it('writes the post with the answers given; blank ones are skipped', async () => {
    const { sent, onStarted } = setup()
    await userEvent.type(screen.getByLabelText('1. Worst chart you ever defended?'), 'A 3D exploding pie')
    await userEvent.click(screen.getByRole('button', { name: 'Write the post with 1 answer' }))
    await waitFor(() => expect(onStarted).toHaveBeenCalled())
    expect(sent().interview[0]).toEqual({ question: 'Worst chart you ever defended?', answer: 'A 3D exploding pie' })
    expect(sent().interview[1].answer).toBe('')
  })

  it('skips the questions', async () => {
    const { sent } = setup()
    await userEvent.type(screen.getByLabelText('2. Who is this for?'), 'Analysts')
    await userEvent.click(screen.getByRole('button', { name: 'Skip the questions' }))
    await waitFor(() => expect(sent()).toBeDefined())
    expect(sent().interview.every((a: { answer: string }) => a.answer === '')).toBe(true)
  })
})
