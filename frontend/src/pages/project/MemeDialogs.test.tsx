import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { MemeFormatOut, MemeInfoOut, MemeLookOut } from '../../api/types.gen'
import { MemeIdeasDialog, MemeWordsDialog } from './MemeDialogs'

const MEME: MemeInfoOut = {
  format: 'terminal',
  format_name: 'Terminal session',
  premise: 'Git blames the meeting.',
  ideas_left: 1,
  has_art: false,
  fallback_from: '',
  look: 'inferno_flat',
  look_label: 'Inferno flat',
  review_verdict: '',
  pitches: [
    {
      index: 0,
      format: 'terminal',
      format_name: 'Terminal session',
      premise: 'Git blames the meeting.',
      words: ['git blame', 'fatal: everyone'],
      tried: true,
      current: true,
      panel_score: 31,
    },
    {
      index: 1,
      format: 'venn',
      format_name: 'Venn diagram',
      premise: 'Only pizza is round and good.',
      words: ['Pizza', 'Pie charts'],
      tried: false,
      current: false,
      panel_score: -60,
    },
  ],
  slots: [
    { name: 'cmd1', hint: 'First command.', text: 'git blame', max_chars: 70, optional: false },
    { name: 'cmd3', hint: 'Third command.', text: '', max_chars: 20, optional: true },
  ],
}
const FORMATS: MemeFormatOut[] = [
  { id: 'terminal', name: 'Terminal session', family: 'artifact', family_label: 'Fake artifacts', when_to_use: '' },
  { id: 'venn', name: 'Venn diagram', family: 'chart', family_label: 'Chart jokes', when_to_use: '' },
]

const LOOKS: MemeLookOut[] = [
  { id: 'inferno_flat', label: 'Inferno flat', description: 'The brand look.', swatch: ['#ed6925', '#781c6d', '#f7d13d', '#cf4446', '#4a0c6b'] },
  { id: 'kawaii', label: 'Kawaii', description: 'Chibi cute.', swatch: ['#ff8fb8', '#9be3c8', '#b9a2ff', '#ffc09f', '#8fd3ff'] },
]

describe('MemeIdeasDialog', () => {
  it('shows the panel score and lets the author draw the meme in another look', async () => {
    const onLook = vi.fn()
    render(
      <MemeIdeasDialog
        open
        onClose={vi.fn()}
        meme={MEME}
        formats={FORMATS}
        looks={LOOKS}
        onLook={onLook}
        onPick={vi.fn()}
        onNext={vi.fn()}
        onFormat={vi.fn()}
      />,
    )
    expect(screen.getByText('Panel 31/40')).toBeInTheDocument()
    expect(screen.getByText('Panel ruled out')).toBeInTheDocument()
    const group = screen.getByRole('group', { name: 'Meme look' })
    expect(within(group).getByRole('button', { name: 'Inferno flat' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(within(group).getByRole('button', { name: 'Kawaii' }))
    expect(onLook).toHaveBeenCalledWith('kawaii')
  })

  it('lists every pitch and lets the author pick one, ask for the next, or change format', async () => {
    const onPick = vi.fn()
    const onNext = vi.fn()
    const onFormat = vi.fn()
    render(<MemeIdeasDialog open onClose={vi.fn()} meme={MEME} formats={FORMATS} onPick={onPick} onNext={onNext} onFormat={onFormat} />)

    const current = screen.getByRole('listitem', { name: /Terminal session: Git blames/ })
    expect(within(current).getByText('Showing now')).toBeInTheDocument()
    expect(within(current).queryByRole('button', { name: 'Use this idea' })).not.toBeInTheDocument()

    const other = screen.getByRole('listitem', { name: /Venn diagram: Only pizza/ })
    expect(within(other).getByText('Pizza / Pie charts')).toBeInTheDocument()
    await userEvent.click(within(other).getByRole('button', { name: 'Use this idea' }))
    expect(onPick).toHaveBeenCalledWith(1)

    await userEvent.click(screen.getByRole('button', { name: 'Next best idea' }))
    expect(onNext).toHaveBeenCalled()
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Meme format' }), 'venn')
    expect(onFormat).toHaveBeenCalledWith('venn')
  })

  it('offers fresh pitches once every idea was tried', () => {
    render(<MemeIdeasDialog open onClose={vi.fn()} meme={{ ...MEME, ideas_left: 0 }} formats={FORMATS} onPick={vi.fn()} onNext={vi.fn()} onFormat={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Pitch five new ideas' })).toBeInTheDocument()
  })
})

describe('MemeWordsDialog', () => {
  it('saves retyped words and will not empty a required slot', async () => {
    const onSave = vi.fn()
    render(<MemeWordsDialog open onClose={vi.fn()} slots={MEME.slots} saving={false} onSave={onSave} />)

    const save = screen.getByRole('button', { name: 'Save words' })
    expect(save).toBeDisabled() // nothing changed yet

    const first = screen.getByLabelText('cmd1')
    await userEvent.clear(first)
    expect(save).toBeDisabled()
    await userEvent.type(first, 'git log')
    await userEvent.type(screen.getByLabelText('cmd3'), 'an optional line that runs long')
    expect(screen.getByText(/long text is drawn smaller/)).toBeInTheDocument()

    await userEvent.click(save)
    expect(onSave).toHaveBeenCalledWith({ cmd1: 'git log', cmd3: 'an optional line that runs long' })
  })

  it('shows why a save failed', () => {
    render(<MemeWordsDialog open onClose={vi.fn()} slots={MEME.slots} saving={false} error="Text slot `cmd1` is empty." onSave={vi.fn()} />)
    expect(screen.getByText(/cmd1/, { selector: 'div, p, span' })).toBeInTheDocument()
  })
})
