import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { ProjectOut, ReferenceOut } from '../../api/types.gen'
import { Article } from '../../components/Article'
import { referenceForHref } from '../../lib/references'
import { ReferenceLink, ReferencesCard } from './ReferencesCard'
import type { ReferenceActions } from './useReferenceActions'

const SOURCE: ReferenceOut = {
  id: 1,
  slot_id: 'r1',
  position: 0,
  kind: 'source',
  placement: 'inline',
  purpose: 'Backs up the claim',
  url: 'https://example.com/paper',
  title: 'A paper about bars',
  speaker: '',
  quote: '',
  status: 'ready',
  error: null,
  in_post: true,
  history: [
    { index: 0, kind: 'source', url: 'https://example.com/old', title: 'Old paper', created_at: '' },
    { index: 1, kind: 'source', url: 'https://example.com/paper', title: 'A paper about bars', created_at: '' },
  ],
}
const QUOTE: ReferenceOut = {
  ...SOURCE,
  id: 2,
  slot_id: 'r2',
  kind: 'quote',
  placement: 'blockquote',
  url: 'https://example.com/box',
  title: 'Box 1976',
  speaker: 'George Box',
  quote: 'All models are wrong, but some are useful.',
  history: [],
}
const FAILED: ReferenceOut = { ...SOURCE, id: 3, kind: 'resource', status: 'error', error: 'Couldn’t find a verifiable resource.', in_post: false, history: [] }

function actions(extra: Partial<ReferenceActions> = {}): ReferenceActions {
  return {
    disabled: false,
    redrawingId: null,
    enriching: false,
    error: null,
    redraw: vi.fn(),
    remove: vi.fn(),
    revert: vi.fn(),
    enrich: vi.fn(),
    ...extra,
  }
}

const project = (references: ReferenceOut[]) => ({ id: 7, references }) as unknown as ProjectOut

describe('ReferencesCard', () => {
  it('lists references with their actions', async () => {
    const a = actions()
    render(<ReferencesCard project={project([SOURCE, QUOTE, FAILED])} actions={a} />)

    expect(screen.getByText('2 of 3 in the post')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'A paper about bars' })).toHaveAttribute('href', 'https://example.com/paper')
    expect(screen.getByText(/All models are wrong/)).toBeInTheDocument()
    expect(screen.getByText(/verifiable resource/)).toBeInTheDocument()

    const source = screen.getByRole('listitem', { name: /Source: A paper about bars/ })
    await userEvent.click(within(source).getByRole('button', { name: 'Redraw' }))
    expect(a.redraw).toHaveBeenCalledWith(SOURCE)
    await userEvent.selectOptions(within(source).getByRole('combobox'), 'quote')
    expect(a.redraw).toHaveBeenCalledWith(SOURCE, 'quote')
    await userEvent.click(within(source).getByRole('button', { name: /Remove source/ }))
    expect(a.remove).toHaveBeenCalledWith(SOURCE)

    await userEvent.click(within(source).getByRole('button', { name: /2 versions/ }))
    await userEvent.click(screen.getByRole('button', { name: /Old paper/ }))
    expect(a.revert).toHaveBeenCalledWith(SOURCE, 0)

    await userEvent.click(screen.getByRole('button', { name: 'Add another' }))
    expect(a.enrich).toHaveBeenCalledWith(1)
  })

  it('offers to find references for a post without any', async () => {
    const a = actions()
    render(<ReferencesCard project={project([])} actions={a} />)
    await userEvent.click(screen.getByRole('button', { name: 'Find references' }))
    expect(a.enrich).toHaveBeenCalledWith(undefined)
  })
})

describe('ReferenceLink', () => {
  it('adds a chip with Redraw and Remove next to reference links only', async () => {
    const a = actions()
    const markdown = '# T\n\n*S*\n\nBars win, as [a paper](https://example.com/paper) shows. A [plain link](https://other.example) too.\n'
    render(
      <Article
        markdown={markdown}
        renderLink={(href, children) => {
          const ref = referenceForHref([SOURCE], href)
          return ref ? (
            <ReferenceLink reference={ref} actions={a}>
              {children}
            </ReferenceLink>
          ) : undefined
        }}
      />,
    )
    expect(screen.getByRole('link', { name: 'plain link' })).toHaveAttribute('href', 'https://other.example')
    const chips = screen.getAllByRole('button', { name: /Show actions/ })
    expect(chips).toHaveLength(1)

    await userEvent.click(chips[0])
    await userEvent.click(within(screen.getByRole('menu')).getByRole('button', { name: 'Redraw' }))
    expect(a.redraw).toHaveBeenCalledWith(SOURCE)
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })
})
