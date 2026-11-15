import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { IdeaLabOut, IdeaOut, IdeaSessionOut, IdeaSourcesOut, PersonaOut } from '../../api/types.gen'
import { IdeaLabPage } from './IdeaLabPage'

const persona = (id: number, name: string, active: boolean) => ({ id, name, is_active: active, is_example: false, voice_profile_version: 1 }) as PersonaOut

const idea = (rank: number, approach: string, label: string, theme: string, extra: Partial<IdeaOut> = {}): IdeaOut => ({
  id: rank,
  session_id: 5,
  persona_id: 1,
  approach,
  approach_label: label,
  theme,
  title: `Idea number ${rank}`,
  brief: `Brief ${rank}`,
  angle: 'Told from experience.',
  outline: ['First point', 'Second point'],
  why_now: 'It is in the news.',
  shelf_life: rank === 1 ? 'this_week' : 'evergreen',
  tags: [],
  evidence: rank === 1 ? [{ url: 'https://example.com/a', title: 'The announcement' }] : [],
  article_type: 'auto',
  builds_on: '',
  scores: { timeliness: 9, demand: 8, fit: 7, differentiation: 6, effort: 5, note: 'Timely and close to home.' },
  score: 10 - rank,
  rank,
  state: 'new',
  stage: 'prospective',
  stage_label: 'Prospective',
  project_id: null,
  note: '',
  prompt: `Idea number ${rank}\n\nOutline:\n- First point`,
  created_at: '2026-11-15T10:00:00',
  ...extra,
})

const SESSION: IdeaSessionOut = {
  id: 5,
  persona_id: 1,
  persona_name: 'Me',
  mode: 'light',
  status: 'ready',
  ideas: 3,
  error: null,
  created_at: '2026-11-15T10:00:00',
  mix: { emerging: 2, builder: 1 },
  focus: '',
  sparks: '',
  notes: [],
  job_id: null,
  items: [
    idea(1, 'emerging', 'Live and Emerging', 'Agents'),
    idea(2, 'builder', 'Portfolio Builder', 'Leadership'),
    idea(3, 'emerging', 'Live and Emerging', 'Leadership'),
  ],
}

const BANK: IdeaOut[] = [
  idea(4, 'builder', 'Portfolio Builder', 'Leadership', { state: 'saved', stage: 'serious', stage_label: 'Serious', note: 'Ask the team first' }),
  idea(5, 'emerging', 'Live and Emerging', 'Agents', {
    state: 'used',
    stage: 'medium_hit',
    stage_label: 'Medium hit',
    project_id: 31,
    project_title: 'The written post',
  }),
  idea(6, 'emerging', 'Live and Emerging', 'Agents', { state: 'dismissed', stage: 'dismissed', stage_label: 'Dismissed' }),
]

const LAB: IdeaLabOut = {
  signals: 40,
  trends: [
    {
      id: 1,
      kind: 'launch',
      label: 'A new agent SDK',
      summary: 'It shipped.',
      heat: 8,
      industries: ['Technology'],
      evidence: [{ url: 'https://example.com/a', title: 'The announcement' }],
      first_seen: '2026-11-15T09:00:00',
      last_seen: '2026-11-15T09:00:00',
    },
  ],
  last_refresh: '2026-11-15T09:00:00+00:00',
  fresh: true,
  scouts_failed: [],
  searches: [],
  active_job_id: null,
}

const SOURCES: IdeaSourcesOut = {
  sources: [
    {
      id: 'tds',
      name: 'A publication',
      group: 'creator',
      group_label: 'Creators and publications',
      url: 'https://example.com/feed',
      enabled: true,
      builtin: true,
      ok: true,
      count: 12,
      error: '',
      checked_at: null,
    },
    {
      id: 'old',
      name: 'A dead feed',
      group: 'vendor',
      group_label: 'Vendors and platforms',
      url: 'https://example.com/old',
      enabled: false,
      builtin: true,
      ok: false,
      count: 0,
      error: 'The source answered 410.',
      checked_at: null,
    },
  ],
  search_only: ['A forum with no feed'],
  voices: ['Ada Lovelace'],
  industries: ['Healthcare'],
}

function setup(path = '/ideas', overrides: { sessions?: unknown; session?: IdeaSessionOut } = {}) {
  const calls: { url: string; method: string; body: unknown }[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    calls.push({ url, method, body: init?.body ? JSON.parse(String(init.body)) : undefined })
    const json = (data: unknown) => new Response(JSON.stringify(data))
    if (url === '/api/personas') return json([persona(1, 'Me', true), persona(2, 'Other voice', false)])
    if (url === '/api/idea-lab') return json(LAB)
    if (url === '/api/idea-lab/sources') return json(SOURCES)
    if (url === '/api/idea-lab/sessions' && method === 'GET') return json(overrides.sessions ?? [{ ...SESSION, items: undefined }])
    if (url === '/api/idea-lab/sessions/5') return json(overrides.session ?? SESSION)
    if (url.startsWith('/api/ideas?')) return json(BANK)
    if (url === '/api/ideas' && method === 'POST')
      return json(idea(9, 'own', 'Your own idea', '', { state: 'saved', stage: 'serious', stage_label: 'Serious' }))
    if (url.startsWith('/api/ideas/') && method === 'PATCH') return json({ ...SESSION.items[0], state: 'saved' })
    if (url === '/api/ideas/1/write') return json({ project: { id: 77 }, job_id: 'job-9' })
    return json({})
  })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <IdeaLabPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return calls
}

afterEach(() => vi.restoreAllMocks())

describe('IdeaLabPage', () => {
  it('shows the ideas best first and regroups them by theme and by source', async () => {
    setup()
    expect(await screen.findByRole('button', { name: 'Idea number 1' })).toBeInTheDocument()
    const titles = () => screen.getAllByRole('button', { name: /^Idea number/ }).map((b) => b.textContent)
    expect(titles()).toEqual(['Idea number 1', 'Idea number 2', 'Idea number 3'])
    expect(screen.getByText('Write this week')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Themes' }))
    const leadership = screen.getByRole('region', { name: 'Leadership' })
    expect(
      within(leadership)
        .getAllByRole('button', { name: /^Idea number/ })
        .map((b) => b.textContent),
    ).toEqual(['Idea number 2', 'Idea number 3'])

    await userEvent.click(screen.getByRole('button', { name: 'Source approach' }))
    expect(screen.getAllByRole('region').map((r) => r.getAttribute('aria-label'))).toEqual(['Live and Emerging', 'Portfolio Builder'])
    expect(titles()).toEqual(['Idea number 1', 'Idea number 3', 'Idea number 2'])
  })

  it('starts a brainstorm with the chosen mode and extras', async () => {
    const calls = setup()
    await userEvent.click(await screen.findByRole('radio', { name: /Medium · 25 ideas/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Steer it' }))
    await userEvent.click(screen.getByRole('checkbox', { name: /Counter-takes/ }))
    await userEvent.type(screen.getByLabelText('What do you want more of?'), 'tutorials')
    await userEvent.click(screen.getByRole('button', { name: 'Brainstorm 25 ideas' }))
    await waitFor(() => expect(calls.some((c) => c.url === '/api/idea-lab/sessions' && c.method === 'POST')).toBe(true))
    expect(calls.find((c) => c.url === '/api/idea-lab/sessions' && c.method === 'POST')?.body).toEqual({
      persona_id: 1,
      mode: 'medium',
      focus: 'tutorials',
      sparks: '',
      extras: ['reader_questions'],
      refresh_research: null,
    })
  })

  it('opens an idea, shows why it ranks, and writes it as another persona', async () => {
    const calls = setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Idea number 1' }))
    expect(screen.getByRole('heading', { name: 'Why it ranks #1' })).toBeInTheDocument()
    expect(screen.getByText('Timely and close to home.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'The announcement' })).toHaveAttribute('href', 'https://example.com/a')
    expect(screen.getByRole('link', { name: 'Customize first' })).toHaveAttribute('href', '/projects/new?idea=1')

    await userEvent.selectOptions(screen.getByLabelText('Write it as'), 'Other voice')
    await userEvent.click(screen.getByRole('button', { name: 'A/B test it' }))
    await waitFor(() => expect(calls.some((c) => c.url === '/api/ideas/1/write')).toBe(true))
    expect(calls.find((c) => c.url === '/api/ideas/1/write')?.body).toEqual({ persona_id: 2, mode: 'ab' })
  })

  it('saves an idea from its card', async () => {
    const calls = setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Save Idea number 1' }))
    await waitFor(() => expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ state: 'saved' }))
    expect(await screen.findByRole('button', { name: 'Remove Idea number 1 from saved' })).toBeInTheDocument()
  })

  it('shows the research with its links and sends another search', async () => {
    const calls = setup('/ideas?tab=research')
    expect(await screen.findByRole('heading', { name: 'A new agent SDK' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'The announcement' })).toHaveAttribute('href', 'https://example.com/a')
    vi.stubGlobal(
      'EventSource',
      class {
        addEventListener() {}
        close() {}
      },
    )
    await userEvent.type(screen.getByLabelText('Send another search'), 'feature stores')
    await userEvent.click(screen.getByRole('button', { name: 'Search and add' }))
    await waitFor(() => expect(calls.find((c) => c.url === '/api/idea-lab/research')?.body).toEqual({ query: 'feature stores', depth: 'standard' }))
    vi.unstubAllGlobals()
  })

  it('lists sources with their health and switches one off', async () => {
    const calls = setup('/ideas?tab=sources')
    expect(await screen.findByText('12 items at the last refresh')).toBeInTheDocument()
    expect(screen.getByText('The source answered 410.')).toBeInTheDocument()
    expect(screen.getByLabelText('Watchlist')).toHaveValue('Ada Lovelace')
    await userEvent.click(screen.getByRole('switch', { name: 'Read A publication' }))
    await waitFor(() => expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({ disabled: ['old', 'tds'] }))
  })

  it('keeps saved ideas in the bank and follows them through the lifecycle', async () => {
    const calls = setup('/ideas?tab=bank')
    // "To write" first: the saved idea with its note.
    expect(await screen.findByRole('button', { name: 'Idea number 4' })).toBeInTheDocument()
    expect(screen.getByText('Ask the team first')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Idea number 5' })).not.toBeInTheDocument()
    expect(calls.find((c) => c.url.startsWith('/api/ideas?'))?.url).toBe('/api/ideas?state=saved&state=used&state=dismissed&persona_id=1')

    await userEvent.click(screen.getByRole('button', { name: 'Published (1)' }))
    expect(screen.getByText('Medium hit')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Idea number 5' }))
    expect(screen.getByRole('list', { name: 'Lifecycle: Medium hit' })).toHaveTextContent('Published · Medium hit')
    expect(screen.getByText(/The written post/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))

    await userEvent.click(screen.getByRole('button', { name: 'Dismissed (1)' }))
    await userEvent.click(screen.getByRole('button', { name: 'Bring back Idea number 6' }))
    await waitFor(() => expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ state: 'new' }))
  })

  it('adds an idea of your own to the bank', async () => {
    const calls = setup('/ideas?tab=bank')
    await userEvent.click(await screen.findByRole('button', { name: 'Add your own idea' }))
    await userEvent.type(screen.getByLabelText('Title'), 'Why our dashboards died')
    await userEvent.type(screen.getByLabelText('Outline'), 'one{enter}{enter}two')
    await userEvent.click(screen.getByRole('button', { name: 'Add to the bank' }))
    await waitFor(() => expect(calls.find((c) => c.url === '/api/ideas' && c.method === 'POST')).toBeTruthy())
    expect(calls.find((c) => c.url === '/api/ideas' && c.method === 'POST')?.body).toEqual({
      persona_id: 1,
      title: 'Why our dashboards died',
      brief: '',
      note: '',
      outline: ['one', 'two'],
    })
  })

  it('invites a first brainstorm when there are none', async () => {
    setup('/ideas', { sessions: [] })
    expect(await screen.findByText('No ideas yet')).toBeInTheDocument()
  })
})
