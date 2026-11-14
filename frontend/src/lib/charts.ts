/** Layout maths for the Insights charts. Pure functions: the components only draw what these return. */

/** The chart series colours, in fixed order (theme tokens, so they follow day and night mode). */
export const SERIES = ['var(--color-chart-1)', 'var(--color-chart-2)', 'var(--color-chart-3)', 'var(--color-chart-4)', 'var(--color-chart-5)']
export const seriesColor = (index: number) => SERIES[index % SERIES.length]

// -- Waffle ---------------------------------------------------------------------------------

/**
 * Split `squares` cells between the slices in proportion to their counts (largest remainder),
 * so the cells always add up and a slice with any share keeps at least its rounded part.
 * Returns the slice index of every cell, in slice order.
 */
export function waffleCells(counts: number[], squares = 50): number[] {
  const total = counts.reduce((sum, n) => sum + Math.max(0, n), 0)
  if (total <= 0 || squares <= 0) return []
  const exact = counts.map((n) => (Math.max(0, n) / total) * squares)
  const cells = exact.map(Math.floor)
  let left = squares - cells.reduce((sum, n) => sum + n, 0)
  const byRemainder = exact.map((value, index) => ({ index, rest: value - Math.floor(value) })).sort((a, b) => b.rest - a.rest || a.index - b.index)
  for (const { index } of byRemainder) {
    if (left <= 0) break
    cells[index] += 1
    left -= 1
  }
  return cells.flatMap((n, index) => Array<number>(n).fill(index))
}

// -- Sankey ---------------------------------------------------------------------------------

export interface FlowNode {
  id: string
  stage: string
  label: string
}

export interface FlowLink {
  source: string
  target: string
  value: number
}

export interface PlacedNode extends FlowNode {
  column: number
  x: number
  y: number
  height: number
  value: number
}

export interface PlacedLink extends FlowLink {
  /** A closed band from the source node to the target node. */
  path: string
  column: number
}

export interface SankeyLayout {
  width: number
  height: number
  nodeWidth: number
  nodes: PlacedNode[]
  links: PlacedLink[]
}

interface SankeyOptions {
  width?: number
  height?: number
  nodeWidth?: number
  /** Vertical space between nodes in a column. */
  gap?: number
  /** The most height one post may take, so a persona with a few posts draws slim bands, not blocks. */
  maxUnit?: number
}

/**
 * Lay out a left-to-right flow through fixed stages. A node is as tall as the posts passing
 * through it; every column uses the same scale, so heights compare across columns.
 */
export function layoutSankey(nodes: FlowNode[], links: FlowLink[], stages: string[], options: SankeyOptions = {}): SankeyLayout {
  const { width = 720, height = 260, nodeWidth = 10, gap = 12, maxUnit = Number.POSITIVE_INFINITY } = options
  const value = (id: string) =>
    Math.max(
      links.filter((l) => l.source === id).reduce((sum, l) => sum + l.value, 0),
      links.filter((l) => l.target === id).reduce((sum, l) => sum + l.value, 0),
    )
  const columns = stages.map((stage) =>
    nodes
      .filter((n) => n.stage === stage)
      .map((n) => ({ ...n, value: value(n.id) }))
      .filter((n) => n.value > 0)
      .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label)),
  )
  const scale = Math.min(...columns.filter((c) => c.length).map((c) => (height - gap * (c.length - 1)) / c.reduce((sum, n) => sum + n.value, 0)), maxUnit)
  if (!Number.isFinite(scale) || scale <= 0) return { width, height, nodeWidth, nodes: [], links: [] }

  const step = stages.length > 1 ? (width - nodeWidth) / (stages.length - 1) : 0
  const placed: PlacedNode[] = []
  columns.forEach((column, index) => {
    const used = column.reduce((sum, n) => sum + n.value * scale, 0) + gap * Math.max(0, column.length - 1)
    let y = (height - used) / 2
    for (const node of column) {
      placed.push({ ...node, column: index, x: index * step, y, height: node.value * scale })
      y += node.value * scale + gap
    }
  })
  const byId = new Map(placed.map((n) => [n.id, n]))

  // Stack each node's links in the order of the nodes they reach, so bands do not cross needlessly.
  const outOffset = new Map<string, number>()
  const inOffset = new Map<string, number>()
  const ordered = links
    .filter((l) => byId.has(l.source) && byId.has(l.target) && l.value > 0)
    .sort((a, b) => {
      const [from, to] = [byId.get(a.source)!, byId.get(b.source)!]
      return from.column - to.column || from.y - to.y || byId.get(a.target)!.y - byId.get(b.target)!.y
    })
  const round = (n: number) => Math.round(n * 10) / 10
  const placedLinks = ordered.map((link) => {
    const source = byId.get(link.source)!
    const target = byId.get(link.target)!
    const thickness = link.value * scale
    const sy = source.y + (outOffset.get(source.id) ?? 0)
    const ty = target.y + (inOffset.get(target.id) ?? 0)
    outOffset.set(source.id, (outOffset.get(source.id) ?? 0) + thickness)
    inOffset.set(target.id, (inOffset.get(target.id) ?? 0) + thickness)
    const x0 = source.x + nodeWidth
    const x1 = target.x
    const mid = (x0 + x1) / 2
    const path = [
      `M${round(x0)},${round(sy)}`,
      `C${round(mid)},${round(sy)} ${round(mid)},${round(ty)} ${round(x1)},${round(ty)}`,
      `L${round(x1)},${round(ty + thickness)}`,
      `C${round(mid)},${round(ty + thickness)} ${round(mid)},${round(sy + thickness)} ${round(x0)},${round(sy + thickness)}`,
      'Z',
    ].join(' ')
    return { ...link, path, column: source.column }
  })
  return { width, height, nodeWidth, nodes: placed, links: placedLinks }
}

// -- Small helpers --------------------------------------------------------------------------

/** A tidy upper bound for an axis that starts at zero. */
export function niceMax(value: number): number {
  if (value <= 0) return 1
  const power = 10 ** Math.floor(Math.log10(value))
  const steps = [1, 1.5, 2, 3, 4, 5, 6, 8, 10]
  return (steps.find((s) => s * power >= value) ?? 10) * power
}

/** 1234.5 -> "1,234.5"; whole numbers lose the decimals. */
export const formatNumber = (value: number) =>
  Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 1 })
