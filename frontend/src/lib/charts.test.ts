import { describe, expect, it } from 'vitest'

import { layoutSankey, niceMax, waffleCells, type FlowLink, type FlowNode } from './charts'

const count = (cells: number[], index: number) => cells.filter((c) => c === index).length

describe('waffleCells', () => {
  it('always fills every square, in slice order', () => {
    const cells = waffleCells([24, 18, 12, 6], 50)
    expect(cells).toHaveLength(50)
    expect([0, 1, 2, 3].map((i) => count(cells, i))).toEqual([20, 15, 10, 5])
    expect(cells).toEqual([...cells].sort((a, b) => a - b))
  })

  it('gives leftover squares to the largest remainders', () => {
    // Thirds of 50 are 16.67 each: two slices get 17, one gets 16.
    const cells = waffleCells([1, 1, 1], 50)
    expect([0, 1, 2].map((i) => count(cells, i))).toEqual([17, 17, 16])
  })

  it('is empty without data', () => {
    expect(waffleCells([], 50)).toEqual([])
    expect(waffleCells([0, 0], 50)).toEqual([])
  })
})

const STAGES = ['article_type', 'opener', 'body', 'closer']
const node = (stage: string, id: string): FlowNode => ({ id: `${stage}:${id}`, stage, label: id })
const NODES = [node('article_type', 'tutorial'), node('article_type', 'opinion'), node('opener', 'auto'), node('body', 'auto'), node('closer', 'auto')]
const LINKS: FlowLink[] = [
  { source: 'article_type:tutorial', target: 'opener:auto', value: 3 },
  { source: 'article_type:opinion', target: 'opener:auto', value: 1 },
  { source: 'opener:auto', target: 'body:auto', value: 4 },
  { source: 'body:auto', target: 'closer:auto', value: 4 },
]

describe('layoutSankey', () => {
  const layout = layoutSankey(NODES, LINKS, STAGES, { width: 400, height: 100, nodeWidth: 10, gap: 10 })
  const at = (id: string) => layout.nodes.find((n) => n.id === id)!

  it('sizes nodes by the posts passing through, on one scale', () => {
    // The first column has two nodes and one gap: (100 - 10) / 4 posts = 22.5 per post.
    expect(at('article_type:tutorial').height).toBeCloseTo(67.5)
    expect(at('article_type:opinion').height).toBeCloseTo(22.5)
    expect(at('opener:auto').height).toBeCloseTo(90)
    expect(at('opener:auto').value).toBe(4)
  })

  it('puts each stage in its own column, biggest node first', () => {
    expect(layout.nodes.map((n) => n.column)).toEqual([0, 0, 1, 2, 3])
    expect(at('closer:auto').x).toBe(390)
    expect(at('article_type:tutorial').y).toBeLessThan(at('article_type:opinion').y)
  })

  it('draws one band per link without overlapping at the target', () => {
    expect(layout.links).toHaveLength(4)
    const [first, second] = layout.links
    // The second band into the opener starts where the first one ends (5 + 67.5).
    expect(first.path.startsWith('M10,0 ')).toBe(true)
    expect(second.path).toContain(' 130,72.5')
  })

  it('draws a single post', () => {
    const one = layoutSankey(
      NODES.slice(2),
      LINKS.slice(2).map((l) => ({ ...l, value: 1 })),
      STAGES.slice(1),
      { height: 80 },
    )
    expect(one.nodes.every((n) => n.height === 80)).toBe(true)
  })

  it('is empty without links', () => {
    expect(layoutSankey(NODES, [], STAGES).nodes).toEqual([])
  })
})

describe('niceMax', () => {
  it('rounds up to a tidy bound', () => {
    expect(niceMax(17.3)).toBe(20)
    expect(niceMax(4.2)).toBe(5)
    expect(niceMax(100)).toBe(100)
    expect(niceMax(0)).toBe(1)
  })
})
