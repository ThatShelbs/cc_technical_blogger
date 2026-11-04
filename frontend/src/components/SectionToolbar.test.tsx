import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { SectionActions } from './SectionToolbar'

describe('SectionActions', () => {
  it('runs each preset action with no brief', async () => {
    const onRun = vi.fn()
    render(<SectionActions onRun={onRun} pending={null} />)
    for (const [label, action] of [
      ['Rewrite', 'rewrite'],
      ['Compact', 'compact'],
      ['Expand', 'expand'],
      ['Add source', 'add_source'],
      ['Add quote', 'add_quote'],
    ] as const) {
      await userEvent.click(screen.getByRole('button', { name: label }))
      expect(onRun).toHaveBeenLastCalledWith({ action, instruction: '' })
    }
  })

  it('sends a typed brief as a custom action', async () => {
    const onRun = vi.fn()
    render(<SectionActions onRun={onRun} pending={null} />)
    await userEvent.click(screen.getByRole('button', { name: 'Custom brief' }))
    const apply = screen.getByRole('button', { name: 'Apply brief' })
    expect(apply).toBeDisabled()
    await userEvent.type(screen.getByLabelText('How should this section change?'), 'make it more positive')
    await userEvent.click(apply)
    expect(onRun).toHaveBeenCalledWith({ action: 'custom', instruction: 'make it more positive' })
  })

  it('shows what is happening while a search-backed action runs', () => {
    render(<SectionActions onRun={vi.fn()} pending="add_source" />)
    expect(screen.getByRole('status')).toHaveTextContent('Searching the web for a source')
    expect(screen.queryByRole('button', { name: 'Compact' })).toBeNull()
  })
})
