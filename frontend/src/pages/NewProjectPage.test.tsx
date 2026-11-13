import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { buildDials, emptyDials } from './dials'
import { NewProjectPage } from './NewProjectPage'

const PERSONA = {
  id: 1,
  name: 'Shelby',
  display_name: 'Shelby Temple',
  is_active: true,
  research_enabled: false,
  default_humor: 6,
  default_education: 'intermediate',
  default_target_words: 1500,
  default_image_count: null,
  default_storytelling: 5,
  default_opinion: 5,
  default_formality: 5,
  default_technical_depth: 5,
  default_skimmability: 5,
  default_include_code: 'auto',
  default_platform: 'medium',
  visual_style: '',
  credit_template: '',
  own_samples: 9,
  influence_samples: 0,
  voice_profile_version: 2,
  voice_profile_label: '',
  latest_voice_profile_version: 2,
  pinned_voice_profile_version: null,
  voice_profile_versions: [],
  active_job_id: null,
  created_at: '2026-10-20T00:00:00Z',
}

describe('buildDials', () => {
  it('sends nothing when nothing changed, so the persona defaults apply', () => {
    expect(buildDials(emptyDials)).toEqual({})
  })

  it('sends only the values the user changed', () => {
    expect(
      buildDials({
        ...emptyDials,
        imageCount: 6,
        humor: 2,
        education: 'expert',
        topic: 'Machine Learning',
        platform: 'linkedin',
        style: { opinion: 9, formality: 3 },
      }),
    ).toEqual({
      image_count: 6,
      humor: 2,
      education: 'expert',
      topic: 'Machine Learning',
      platform: 'linkedin',
      opinion: 9,
      formality: 3,
    })
  })
})

const option = (id: string, label: string, group: string) => ({ id, label, summary: `${label} summary`, group, guide: '' })
const CATALOG = {
  article_types: [
    {
      id: 'tutorial',
      label: 'Tutorial',
      summary: 'Teach by building.',
      guide: '',
      openers: ['result_first'],
      bodies: ['progressive_build'],
      closers: ['challenge'],
    },
  ],
  openers: [option('joke_confession', 'Joke: the confession', 'Joke'), option('result_first', 'Show the result first', 'Story')],
  bodies: [option('progressive_build', 'Start simple, build up', 'Teach')],
  closers: [option('challenge', 'A challenge', 'Hand it over'), option('kicker', 'One-line kicker', 'Land it')],
}

function renderPage() {
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
}

describe('NewProjectPage', () => {
  it('builds a formula from an article type, its classic parts, a swapped opener and a note', async () => {
    const saved: unknown[] = []
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input)
      if (url === '/api/personas') return new Response(JSON.stringify([{ ...PERSONA, default_formula: { closer: 'kicker' } }]))
      if (url === '/api/formulas/catalog') return new Response(JSON.stringify(CATALOG))
      if (url === '/api/formulas' && init?.method === 'POST') {
        saved.push({ id: 1, description: '', label: '', created_at: '', ...JSON.parse(String(init.body)) })
        return new Response(JSON.stringify(saved[0]), { status: 201 })
      }
      if (url === '/api/formulas') return new Response(JSON.stringify(saved))
      if (url === '/api/projects') return new Response(JSON.stringify({ project: { id: 42 }, job_id: 'job1' }), { status: 201 })
      return new Response('{}')
    })
    renderPage()

    await userEvent.selectOptions(await screen.findByLabelText('Article type'), await screen.findByRole('option', { name: 'Tutorial' }))
    expect(screen.getByText('Teach by building.')).toBeInTheDocument()
    // The persona's default closer is already in view, so the builder starts open.
    expect(screen.getByLabelText('Closer')).toHaveValue('kicker')
    await userEvent.click(screen.getByRole('button', { name: /Use the classic tutorial formula/ }))
    expect(screen.getByLabelText('Opener')).toHaveValue('result_first')
    expect(screen.getByLabelText('Body')).toHaveValue('progressive_build')
    await userEvent.selectOptions(screen.getByLabelText('Opener'), 'joke_confession')
    await userEvent.type(screen.getByLabelText('Your own instructions for the opener'), 'Mention the notebook')

    // Save it under a name to reuse later.
    await userEvent.click(screen.getByRole('button', { name: /Save as a formula/ }))
    await userEvent.type(screen.getByLabelText('Formula name'), 'Confess and build{Enter}')
    expect(await screen.findByRole('option', { name: 'Confess and build' })).toBeInTheDocument()
    expect(saved[0]).toMatchObject({ name: 'Confess and build', article_type: 'tutorial', opener: 'joke_confession', closer: 'challenge' })

    await userEvent.type(screen.getByLabelText(/What should this post be about/), 'Sizing an A/B test')
    await userEvent.click(screen.getByRole('button', { name: /Write my post/ }))
    await waitFor(() => expect(screen.getByText('Opened project')).toBeInTheDocument())
    const post = fetchMock.mock.calls.find(([url, init]) => url === '/api/projects' && init?.method === 'POST')
    expect(JSON.parse(String(post?.[1]?.body)).dials).toEqual({
      article_type: 'tutorial',
      opener: 'joke_confession',
      body: 'progressive_build',
      closer: 'challenge',
      opener_note: 'Mention the notebook',
    })
  })

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

    expect(await screen.findByText('Writing as Shelby · voice profile v2')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/What should this post be about/), 'Why A/B tests are underpowered')
    await userEvent.click(screen.getByRole('button', { name: /Write my post/ }))

    await waitFor(() => expect(screen.getByText('Opened project')).toBeInTheDocument())
    const post = fetchMock.mock.calls.find(([url, init]) => url === '/api/projects' && init?.method === 'POST')
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      prompt: 'Why A/B tests are underpowered',
      dials: {},
      persona_id: 1,
    })
  })
})
