import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import type { PersonaInsightsOut } from '../../api/types.gen'
import { InsightsTab } from './InsightsTab'

const EMPTY: PersonaInsightsOut = {
  overview: { persona_name: 'Me', own_samples: 0, influence_samples: 0, own_words: 0, voice_profile_version: null, updated_at: null },
  digest: null,
  fingerprint: null,
  openers: [],
  phrases: [],
  formula: { posts: 0, nodes: [], links: [] },
  track_record: {
    posts: 0,
    published: 0,
    words: 0,
    images: 0,
    references: 0,
    stages: [],
    outcomes: [],
    points: [],
    meme_formats: [],
    lessons: [],
    playbook: 0,
  },
}

const point = (id: number, voice: number) => ({
  project_id: id,
  title: `Post ${id}`,
  created_at: '2026-11-01T00:00:00',
  stage: 'draft',
  outcome: null,
  words: 900,
  authenticity: 80,
  voice_match: voice,
  critique: 8,
})

const FULL: PersonaInsightsOut = {
  overview: { persona_name: 'Me', own_samples: 14, influence_samples: 0, own_words: 21380, voice_profile_version: 2, updated_at: '2026-11-13T12:00:00' },
  digest: {
    headline: 'Mostly chatty, backed up by data.',
    tone: ['Casual, self-deprecating, a little nerdy', 'Talks straight to you, the reader'],
    signature_phrases: ['Yikes.', 'Fair warning:'],
    steer_clear: ['Hype words: revolutionary, game-changer'],
    voice_mix: [
      { name: 'Chatty', description: 'Talks to the reader', count: 24, share: 40 },
      { name: 'Data', description: 'Numbers and evidence', count: 18, share: 30 },
      { name: 'Jokes', description: 'Asides and punchlines', count: 12, share: 20 },
      { name: 'How-to', description: 'Steps to follow', count: 6, share: 10 },
    ],
    sentences_sampled: 60,
    sentences_labeled: 60,
    image_habits: ['About 1 image every 175 words'],
    caption_example: 'Visualization by Me',
    generated_at: '2026-11-13T12:00:00',
    version: 2,
    stale: false,
  },
  fingerprint: {
    reference_label: 'A typical tech blog (approximate)',
    reference_kind: 'typical',
    rows: [{ key: 'avg_sentence_words', label: 'Words per sentence', you: 10.2, reference: 19, unit: 'words' }],
  },
  openers: [{ id: 'question', label: 'A question', count: 9 }],
  phrases: [{ id: 'should be a piece of cake', label: 'Should be a piece of cake', count: 4 }],
  formula: {
    posts: 2,
    nodes: [
      { id: 'article_type:tutorial', stage: 'article_type', label: 'Tutorial' },
      { id: 'opener:auto', stage: 'opener', label: 'Your usual' },
      { id: 'body:step_by_step', stage: 'body', label: 'Step by step' },
      { id: 'closer:takeaways', stage: 'closer', label: 'Key takeaways' },
    ],
    links: [
      { source: 'article_type:tutorial', target: 'opener:auto', value: 2 },
      { source: 'opener:auto', target: 'body:step_by_step', value: 2 },
      { source: 'body:step_by_step', target: 'closer:takeaways', value: 2 },
    ],
  },
  track_record: {
    ...EMPTY.track_record,
    posts: 2,
    published: 1,
    words: 1800,
    images: 8,
    references: 10,
    outcomes: [{ id: 'good', label: 'good', count: 1 }],
    points: [point(1, 70), point(2, 82)],
    meme_formats: [{ id: 'classic_caption', label: 'Classic caption', count: 2 }],
    lessons: [{ kind: 'replace', old: 'utilize', new: 'use', count: 3 }],
  },
}

function setup(data: PersonaInsightsOut) {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, init) => {
    if (init?.method === 'POST') return new Response(JSON.stringify({ id: 'job-1', kind: 'voice_insights', status: 'queued' }))
    return new Response(JSON.stringify(data))
  })
  const onOpenTab = vi.fn()
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <InsightsTab personaId={7} onOpenTab={onOpenTab} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { fetchMock, onOpenTab }
}

describe('InsightsTab', () => {
  it('sends a persona with no writing to the samples tab', async () => {
    const { onOpenTab } = setup(EMPTY)
    await userEvent.click(await screen.findByRole('button', { name: 'Add writing samples' }))
    expect(onOpenTab).toHaveBeenCalledWith('samples')
  })

  it('shows the measured charts and offers the voice profile before there is a digest', async () => {
    const { onOpenTab } = setup({ ...FULL, digest: null, overview: { ...FULL.overview, voice_profile_version: null } })
    expect(await screen.findByText('Style fingerprint')).toBeInTheDocument()
    expect(screen.queryByText('Voice mix')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Refresh insights' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Go to voice profile' }))
    expect(onOpenTab).toHaveBeenCalledWith('voice')
  })

  it('draws the digest, the voice mix and the charts', async () => {
    setup(FULL)
    expect(await screen.findByText('Built from 14 writing samples · 21,380 words', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('Casual, self-deprecating, a little nerdy')).toBeInTheDocument()
    expect(screen.getByText('Fair warning:')).toBeInTheDocument()
    expect(screen.getByText('Hype words: revolutionary, game-changer')).toBeInTheDocument()
    expect(screen.getByText('Mostly chatty, backed up by data.')).toBeInTheDocument()
    expect(screen.getByText('Visualization by Me')).toBeInTheDocument()

    // 50 squares, split 20 / 15 / 10 / 5.
    const waffle = screen.getByRole('img', { name: 'Voice mix: Chatty 40%, Data 30%, Jokes 20%, How-to 10%' })
    expect(waffle.children).toHaveLength(50)
    expect(within(waffle).getAllByTitle(/^Jokes: 20%/)).toHaveLength(10)

    expect(screen.getByRole('img', { name: 'Formula flow across 2 posts' })).toBeInTheDocument()
    expect(screen.getByText('Tutorial to Your usual: 2 posts')).toBeInTheDocument()
    expect(screen.getByText('10.2')).toBeInTheDocument()
    expect(screen.getByText('Good traction · 1')).toBeInTheDocument()
    expect(screen.getByText(/utilize/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Post 2' })).toHaveAttribute('href', '/projects/2')
  })

  it('says when the summary is from an older version and refreshes it', async () => {
    const { fetchMock } = setup({ ...FULL, digest: { ...FULL.digest!, version: 1, stale: true } })
    expect(await screen.findByText(/This summary describes voice profile v1; you now use v2/)).toBeInTheDocument()
    vi.stubGlobal(
      'EventSource',
      class {
        addEventListener() {}
        close() {}
      },
    )
    await userEvent.click(screen.getByRole('button', { name: 'Refresh insights' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) => url === '/api/personas/7/insights/refresh' && init?.method === 'POST')).toBe(true))
    vi.unstubAllGlobals()
  })
})
