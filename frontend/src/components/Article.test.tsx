import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { ImageOut } from '../api/types.gen'
import { fullCaption, splitArticle, splitHeader } from '../lib/article'
import { Article } from './Article'

const POST = `# Pie Charts Are Lame

*A friendly roast.*

{{image:hero}}

Intro paragraph.

## Section

Body text.

{{image:meme}}
`

function image(slot: string, extra: Partial<ImageOut> = {}): ImageOut {
  return {
    id: 1,
    slot_id: slot,
    position: 0,
    kind: 'hero',
    purpose: '',
    prompt: '',
    alt: `${slot} alt`,
    caption: 'A sad pie',
    credit: 'Author: Shelby; Made with FLUX',
    provider: 'cloudflare-flux',
    seed: 1,
    width: 10,
    height: 10,
    url: `/api/images/1/file?v=${slot}`,
    status: 'ready',
    error: null,
    history: [],
    ...extra,
  }
}

describe('splitArticle', () => {
  it('splits text and image slots in order', () => {
    const parts = splitArticle(splitHeader(POST).body)
    expect(parts.map((p) => (p.type === 'image' ? `img:${p.slot}` : 'text'))).toEqual(['img:hero', 'text', 'img:meme'])
  })

  it('only treats placeholders on their own line as images', () => {
    expect(splitArticle('Inline {{image:hero}} is just text.')).toEqual([{ type: 'text', text: 'Inline {{image:hero}} is just text.' }])
  })
})

describe('splitHeader', () => {
  it('extracts the title and italic subtitle', () => {
    const { title, subtitle, body } = splitHeader(POST)
    expect(title).toBe('Pie Charts Are Lame')
    expect(subtitle).toBe('A friendly roast.')
    expect(body).not.toContain('# Pie Charts')
  })

  it('does not mistake bold text for a subtitle', () => {
    expect(splitHeader('# T\n\n**Bold start** of a paragraph.').subtitle).toBe('')
  })
})

describe('fullCaption', () => {
  it('joins caption and credit like a blog caption', () => {
    expect(fullCaption({ caption: 'A sad pie', credit: 'Author: S' })).toBe('A sad pie; Author: S')
    expect(fullCaption({ caption: 'Done.', credit: 'Author: S' })).toBe('Done. Author: S')
    expect(fullCaption({ caption: 'Pie. Author: S', credit: 'Author: S' })).toBe('Pie. Author: S')
    expect(fullCaption({ caption: '', credit: 'Author: S' })).toBe('Author: S')
  })
})

describe('Article', () => {
  it('renders the post with captioned images inline', () => {
    render(<Article markdown={POST} images={[image('hero'), image('meme', { id: 2, caption: 'Pie logic' })]} />)
    expect(screen.getByRole('heading', { level: 1, name: 'Pie Charts Are Lame' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'Section' })).toBeInTheDocument()
    expect(screen.getByAltText('hero alt')).toBeInTheDocument()
    expect(screen.getByText('Pie logic; Author: Shelby; Made with FLUX')).toBeInTheDocument()
  })
})
