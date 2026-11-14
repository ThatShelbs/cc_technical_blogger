import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { ProjectOut } from '../../api/types.gen'
import { StageControl } from './StageControl'

const PROJECT = { id: 3, stage: 'ready', outcome: null } as unknown as ProjectOut

function setup(project: ProjectOut = PROJECT) {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify(project)))
  render(
    <QueryClientProvider client={new QueryClient()}>
      <StageControl project={project} />
    </QueryClientProvider>,
  )
  const patched = () => {
    const call = fetchMock.mock.calls.find(([url, init]) => url === '/api/projects/3' && init?.method === 'PATCH')
    return call?.[1]?.body ? JSON.parse(String(call[1].body)) : undefined
  }
  return { patched }
}

describe('StageControl', () => {
  it('shows the stage and hides the outcome until published', () => {
    setup()
    expect(screen.getByRole('button', { name: 'Ready' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByRole('group', { name: 'How it did' })).not.toBeInTheDocument()
  })

  it('publishes the post', async () => {
    const { patched } = setup()
    await userEvent.click(screen.getByRole('button', { name: 'Published' }))
    await waitFor(() => expect(patched()).toEqual({ stage: 'published' }))
  })

  it('rates a published post', async () => {
    const { patched } = setup({ ...PROJECT, stage: 'published', outcome: 'too_early' } as ProjectOut)
    expect(screen.getByRole('button', { name: 'Too early' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Viral' }))
    await waitFor(() => expect(patched()).toEqual({ outcome: 'viral' }))
  })
})
