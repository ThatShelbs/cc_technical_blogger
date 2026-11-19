import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ImageOut } from '../../api/types.gen'
import { ImageCard } from './ImageCard'

const HERO = {
  id: 7,
  slot_id: 'hero',
  kind: 'hero',
  status: 'ready',
  provider: 'claude-opening',
  url: '/files/hero.png',
  alt: 'An opening image',
  caption: '',
  credit: '',
  purpose: 'Opening image',
  rating: 0,
  history: [],
  opening: {
    style: 'editorial',
    style_label: 'Visual metaphor',
    template: '',
    mode: 'svg',
    summary: '',
    ideas_left: 0,
    fallback_from: '',
    pitches: [],
    sources: [],
    slots: [],
    thumbnail_fit: 'cover',
    review: { why: 'It reads at a glance.', readings: ['A ghost juggling notebooks'] },
  },
} as unknown as ImageOut

function setup(image: ImageOut = HERO) {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
    const body = String(url).endsWith('/rating') ? image : []
    return new Response(JSON.stringify(body))
  })
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ImageCard projectId={3} image={image} images={[image]} title="Why my notebooks multiply" />
    </QueryClientProvider>,
  )
  const rated = () => {
    const call = fetchMock.mock.calls.find(([url, init]) => url === '/api/images/7/rating' && init?.method === 'PUT')
    return call?.[1]?.body ? JSON.parse(String(call[1].body)) : undefined
  }
  return { rated }
}

afterEach(() => vi.restoreAllMocks())

describe('ImageCard', () => {
  it('rates the opening image', async () => {
    const { rated } = setup()
    await userEvent.click(screen.getByRole('button', { name: 'I like this one' }))
    await waitFor(() => expect(rated()).toEqual({ rating: 1 }))
  })

  it('clears a thumbs up when clicked again', async () => {
    const { rated } = setup({ ...HERO, rating: 1 } as ImageOut)
    const up = screen.getByRole('button', { name: 'I like this one' })
    expect(up).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(up)
    await waitFor(() => expect(rated()).toEqual({ rating: 0 }))
  })

  it('shows why the panel picked it and a feed card preview with the title', async () => {
    setup()
    expect(screen.getByLabelText('Why the panel picked this one')).toHaveTextContent('Why this one: It reads at a glance.')
    expect(screen.queryByLabelText('Feed card preview')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Feed preview' }))
    expect(screen.getByLabelText('Feed card preview')).toHaveTextContent('Why my notebooks multiply')
  })

  it('offers no rating on an ordinary image', () => {
    setup({ ...HERO, kind: 'diagram', slot_id: 'img1', opening: null } as unknown as ImageOut)
    expect(screen.queryByRole('button', { name: 'I like this one' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Feed preview' })).not.toBeInTheDocument()
  })
})
