import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ProjectOut } from '../../api/types.gen'
import { PostSettingsDialog } from './PostSettingsDialog'

const persona = (id: number, name: string, version: number | null) => ({
  id,
  name,
  is_active: id === 1,
  default_humor: 5,
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
  voice_profile_version: version,
})

const PROJECT = {
  id: 7,
  persona_id: 1,
  prompt: 'Pie charts are lame',
  dials: { humor: 8, revision_passes: 0 },
  plan: { chosen_title: 'Pie Charts Are Lame', sections: [{ heading: 'Why People Love Pies', key_points: ['they look friendly'] }] },
} as unknown as ProjectOut

afterEach(() => vi.restoreAllMocks())

describe('PostSettingsDialog', () => {
  it('shows the original brief, borrows the planned outline, and regenerates with the new settings', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      if (String(input) === '/api/personas')
        return new Response(JSON.stringify([persona(1, 'Shelby', 2), persona(2, 'Formal Me', 1), persona(3, 'Empty', null)]))
      return new Response(JSON.stringify({ id: 'job9', kind: 'generate_post' }), { status: 202 })
    })
    const onStarted = vi.fn()
    render(
      <QueryClientProvider client={new QueryClient()}>
        <PostSettingsDialog project={PROJECT} open onClose={() => {}} onStarted={onStarted} />
      </QueryClientProvider>,
    )

    const brief = screen.getByLabelText(/Brief or outline/)
    expect(brief).toHaveValue('Pie charts are lame')
    await userEvent.click(screen.getByRole('button', { name: /Outline Claude planned/ }))
    await userEvent.click(screen.getByRole('button', { name: /Use as my outline/ }))
    expect(brief).toHaveValue('Pie Charts Are Lame\n- Why People Love Pies\n  - they look friendly')
    await userEvent.type(brief, '\n- a tiny matplotlib example')

    // Only personas with a voice profile can write.
    await waitFor(() => expect(screen.getByRole('option', { name: 'Formal Me' })).toBeInTheDocument())
    expect(screen.queryByRole('option', { name: /Empty/ })).not.toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Persona'), '2')
    await userEvent.selectOptions(screen.getByLabelText('Publishing on'), 'x')
    await userEvent.type(screen.getByLabelText(/Audience/), 'analytics leads')
    await userEvent.click(screen.getByRole('button', { name: /Regenerate with these settings/ }))

    await waitFor(() => expect(onStarted).toHaveBeenCalled())
    const call = fetchMock.mock.calls.find(([url]) => url === '/api/projects/7/generate')
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      prompt: 'Pie Charts Are Lame\n- Why People Love Pies\n  - they look friendly\n- a tiny matplotlib example',
      persona_id: 2,
      dials: { humor: 8, audience: 'analytics leads', platform: 'x', revision_passes: 0 },
    })
  })
})
