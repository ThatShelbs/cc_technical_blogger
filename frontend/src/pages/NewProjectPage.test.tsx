import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { buildDials, type DialsState } from './dials'
import { NewProjectPage } from './NewProjectPage'

const PERSONA = {
  id: 1,
  name: 'Shelby',
  display_name: 'Shelby Temple',
  is_active: true,
  research_enabled: false,
  default_humor: 6,
  default_education: 'intermediate',
  visual_style: '',
  credit_template: '',
  own_samples: 9,
  influence_samples: 0,
  voice_soul_version: 2,
  active_job_id: null,
  created_at: '2026-10-20T00:00:00Z',
}

const BASE: DialsState = {
  targetWords: 1500,
  autoImages: true,
  imageCount: 4,
  humor: null,
  education: null,
  topic: '',
  platform: 'medium',
  includeCode: 'auto',
}

describe('buildDials', () => {
  it('sends only the platform when not customized, so backend defaults apply', () => {
    expect(buildDials(false, { ...BASE, humor: 9 })).toEqual({ platform: 'medium' })
  })

  it('sends only the values the user changed', () => {
    expect(buildDials(true, BASE)).toEqual({ target_words: 1500, platform: 'medium', include_code: 'auto' })
    expect(buildDials(true, { ...BASE, autoImages: false, imageCount: 6, humor: 2, education: 'expert', topic: 'Machine Learning' })).toEqual({
      target_words: 1500,
      platform: 'medium',
      include_code: 'auto',
      image_count: 6,
      humor: 2,
      education: 'expert',
      topic: 'Machine Learning',
    })
  })
})

describe('NewProjectPage', () => {
  it('creates a post from just a prompt and opens it', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input)
      if (url === '/api/personas') return new Response(JSON.stringify([PERSONA]))
      if (url === '/api/projects' && init?.method === 'POST') {
        return new Response(JSON.stringify({ project: { id: 42 }, job_id: 'job1' }), { status: 201 })
      }
      return new Response('{}')
    })

    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={['/projects/new']}>
          <Routes>
            <Route path="/projects/new" element={<NewProjectPage />} />
            <Route path="/projects/:id" element={<p>Opened project</p>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(await screen.findByText('Writing as Shelby')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/What should this post be about/), 'Why A/B tests are underpowered')
    await userEvent.click(screen.getByRole('button', { name: /Write my post/ }))

    await waitFor(() => expect(screen.getByText('Opened project')).toBeInTheDocument())
    const post = fetchMock.mock.calls.find(([url, init]) => url === '/api/projects' && init?.method === 'POST')
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      prompt: 'Why A/B tests are underpowered',
      dials: { platform: 'medium' },
      persona_id: 1,
    })
  })
})
