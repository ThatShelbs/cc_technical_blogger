import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ProjectOut } from '../../api/types.gen'
import { TitlePicker } from './ProjectPage'

const PROJECT = {
  id: 7,
  title: 'Nobody Has a Single Source of Truth',
  pinned_titles: [] as string[],
  plan: { title_options: ['Nobody Has a Single Source of Truth', 'Single Source of Truth Is a Myth', 'A Quick Reality Check'] },
} as unknown as ProjectOut

function setup(project: ProjectOut = PROJECT) {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify(project)))
  render(
    <QueryClientProvider client={new QueryClient()}>
      <TitlePicker project={project} />
    </QueryClientProvider>,
  )
  const body = (path: string, method: string) => {
    const call = fetchMock.mock.calls.find(([url, init]) => url === path && init?.method === method)
    return call?.[1]?.body ? JSON.parse(String(call[1].body)) : call && {}
  }
  return { fetchMock, body }
}

afterEach(() => vi.restoreAllMocks())

describe('TitlePicker', () => {
  it('pins an option', async () => {
    const { body } = setup()
    await userEvent.click(screen.getByRole('button', { name: 'Pin “Single Source of Truth Is a Myth”' }))
    await waitFor(() => expect(body('/api/projects/7', 'PATCH')).toEqual({ pinned_titles: ['Single Source of Truth Is a Myth'] }))
  })

  it('asks for new options', async () => {
    const { body } = setup()
    await userEvent.click(screen.getByRole('button', { name: /New options/ }))
    await waitFor(() => expect(body('/api/projects/7/titles', 'POST')).toBeTruthy())
  })

  it('saves an edited title', async () => {
    const { body } = setup()
    const input = screen.getByLabelText('Post title')
    await userEvent.clear(input)
    await userEvent.type(input, 'Nobody Has One Source of Truth')
    await userEvent.click(screen.getByRole('button', { name: 'Save title' }))
    await waitFor(() => expect(body('/api/projects/7', 'PATCH')).toEqual({ title: 'Nobody Has One Source of Truth' }))
  })

  it('shows a hand-edited title as the selected first option', () => {
    setup({ ...PROJECT, title: 'My Own Title' } as ProjectOut)
    const first = screen.getAllByRole('listitem')[0]
    expect(first).toHaveTextContent('My Own Title')
    expect(screen.getByRole('button', { name: 'My Own Title' })).toHaveAttribute('aria-pressed', 'true')
  })
})
