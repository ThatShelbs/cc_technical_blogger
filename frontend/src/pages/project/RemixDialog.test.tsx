import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { ImageOut, MemeFormatOut, OpeningInfoOut, RemixDimensionOut } from '../../api/types.gen'
import { buildOnChoices, dependentsOf, remixSummary, remixTwists } from '../../lib/remix'
import { OpeningIdeasDialog } from './OpeningDialogs'
import { RemixDialog } from './RemixDialog'

function image(slot: string, position: number, extra: Partial<ImageOut> = {}): ImageOut {
  return {
    id: position + 1,
    slot_id: slot,
    position,
    kind: 'chart',
    purpose: `Purpose ${slot}`,
    prompt: '',
    alt: '',
    caption: `Caption ${slot}`,
    credit: '',
    provider: 'vega-lite',
    seed: null,
    width: 100,
    height: 100,
    url: null,
    status: 'ready',
    error: null,
    history: [],
    builds_on: '',
    remix: null,
    remix_dimensions: ['palette'],
    ...extra,
  }
}

const DIMENSIONS: RemixDimensionOut[] = [
  {
    id: 'palette',
    label: 'Colors',
    options: [
      { id: 'viridis', label: 'Viridis', swatch: ['#440154', '#21918c', '#fde725'] },
      { id: 'ocean', label: 'Ocean', swatch: [] },
    ],
  },
  {
    id: 'cast',
    label: 'Who is in it',
    options: [
      { id: 'ghost', label: 'The ghost', swatch: [] },
      { id: 'dogs', label: 'Dogs', swatch: [] },
    ],
  },
  { id: 'staging', label: 'Staging', options: [{ id: 'wide', label: 'Wide shot', swatch: [] }] },
]

describe('RemixDialog', () => {
  it('offers only what this image can vary and sends the pins, leaving the rest to chance', async () => {
    const onRemix = vi.fn()
    const hero = image('hero', 0, { kind: 'hero', remix_dimensions: ['palette', 'cast'] })
    render(<RemixDialog open onClose={() => {}} image={hero} dimensions={DIMENSIONS} onRemix={onRemix} />)

    expect(screen.getByLabelText('Colors')).toBeInTheDocument()
    expect(screen.queryByLabelText('Staging')).not.toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Who is in it'), 'dogs')
    await userEvent.click(screen.getByRole('button', { name: 'Remix' }))
    expect(onRemix).toHaveBeenCalledWith({ cast: 'dogs' }, true)

    await userEvent.selectOptions(screen.getByLabelText('Colors'), 'viridis')
    await userEvent.click(screen.getByRole('switch'))
    await userEvent.click(screen.getByRole('button', { name: 'Remix' }))
    expect(onRemix).toHaveBeenLastCalledWith({ cast: 'dogs', palette: 'viridis' }, false)
  })
})

describe('remix helpers', () => {
  it('says what the last redraw fixed and tried', () => {
    const remix = {
      weakness: 'Cluttered.',
      improvements: ['Cut the legend.'],
      fresh_angle: '',
      tweaks: [
        { dimension: 'palette', id: 'viridis', label: 'Viridis' },
        { dimension: 'cast', id: 'dogs', label: 'Dogs' },
      ],
      brainstormed: true,
    }
    expect(remixTwists(remix)).toBe('colors: Viridis, cast: Dogs')
    expect(remixSummary(remix)).toBe('fixed "Cut the legend"; tried colors: Viridis, cast: Dogs')
    expect(remixSummary(null)).toBe('')
  })

  it('lets an image build only on earlier drawn images, and follows the chain of dependents', () => {
    const images = [
      image('hero', 0, { kind: 'hero' }),
      image('img2', 1),
      image('img3', 2, { builds_on: 'img2' }),
      image('img4', 3, { builds_on: 'img3' }),
      image('img5', 4, { provider: 'upload' }),
      image('meme', 5, { kind: 'meme' }),
    ]
    expect(buildOnChoices(images[3], images).map((i) => i.slot_id)).toEqual(['img2', 'img3'])
    expect(buildOnChoices(images[1], images)).toEqual([])
    expect(buildOnChoices(images[5], images)).toEqual([])
    expect(dependentsOf(images[1], images)).toEqual(['img3', 'img4'])
    expect(dependentsOf(images[3], images)).toEqual([])
  })
})

describe('OpeningIdeasDialog meme bank', () => {
  it('opens the post with any meme format from the bank', async () => {
    const opening: OpeningInfoOut = {
      style: 'editorial',
      style_label: 'Visual metaphor',
      template: '',
      mode: 'auto',
      summary: '',
      ideas_left: 0,
      fallback_from: '',
      pitches: [],
      sources: [],
      review: null,
      slots: [],
      thumbnail_fit: 'cover',
    }
    const formats: MemeFormatOut[] = [
      { id: 'venn', name: 'Venn diagram', family: 'chart', family_label: 'Chart jokes', when_to_use: '' },
      { id: 'right_right', name: 'For the better, right?', family: 'classic', family_label: 'Famous formats', when_to_use: '' },
    ]
    const onMemeFormat = vi.fn()
    render(
      <OpeningIdeasDialog
        open
        onClose={() => {}}
        opening={opening}
        styles={[]}
        onPick={() => {}}
        onNext={() => {}}
        onStyle={() => {}}
        memeFormats={formats}
        onMemeFormat={onMemeFormat}
      />,
    )
    await userEvent.selectOptions(screen.getByLabelText('Open with a meme'), 'right_right')
    expect(onMemeFormat).toHaveBeenCalledWith('right_right')
  })
})
