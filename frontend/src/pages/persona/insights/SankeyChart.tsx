import { useState } from 'react'

import type { FormulaFlowOut } from '../../../api/types.gen'
import { layoutSankey, seriesColor } from '../../../lib/charts'

const STAGES = ['article_type', 'opener', 'body', 'closer']
const STAGE_LABELS = ['Article type', 'Opener', 'Body', 'Closer']
const WIDTH = 720
/** Space kept on the right for the last column's labels, so every label sits to the right of its node. */
const LABEL_ROOM = 150
const HEADER = 24
const GAP = 18
/** The most height one post takes. */
const UNIT = 30
const MAX_LABEL = 24
const posts = (n: number) => `${n} ${n === 1 ? 'post' : 'posts'}`
const short = (label: string) => (label.length > MAX_LABEL ? `${label.slice(0, MAX_LABEL - 1).trimEnd()}…` : label)

/** How the persona's posts flow through the formula: article type, opener, body, closer. Band width = number of posts. */
export function SankeyChart({ flow }: { flow: FormulaFlowOut }) {
  const [active, setActive] = useState<string | null>(null)
  const tallest = Math.max(...STAGES.map((stage) => flow.nodes.filter((n) => n.stage === stage).length), 1)
  // Room for every node's label, and for the posts themselves once there are many.
  const height = Math.max(tallest * 46, Math.min(260, flow.posts * UNIT + (tallest - 1) * GAP), 64)
  const layout = layoutSankey(flow.nodes, flow.links, STAGES, { width: WIDTH - LABEL_ROOM, height, nodeWidth: 10, gap: GAP, maxUnit: UNIT })
  const label = new Map(layout.nodes.map((n) => [n.id, n.label]))
  const touches = (link: { source: string; target: string }) => active === null || link.source === active || link.target === active
  const step = (WIDTH - LABEL_ROOM - layout.nodeWidth) / (STAGES.length - 1)

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${WIDTH} ${height + HEADER}`} className="w-full min-w-[640px]" role="img" aria-label={`Formula flow across ${posts(flow.posts)}`}>
        {STAGE_LABELS.map((stage, column) => (
          <text key={stage} x={column * step} y={11} className="fill-muted text-[11px] font-semibold tracking-wide uppercase">
            {stage}
          </text>
        ))}
        <g transform={`translate(0 ${HEADER})`}>
          {layout.links.map((link) => (
            <path
              key={`${link.source}>${link.target}`}
              d={link.path}
              fill={seriesColor(link.column)}
              opacity={touches(link) ? (active ? 0.6 : 0.32) : 0.08}
              className="transition-opacity"
            >
              <title>{`${label.get(link.source)} → ${label.get(link.target)}: ${posts(link.value)}`}</title>
            </path>
          ))}
          {layout.nodes.map((node) => (
            <g key={node.id} onMouseEnter={() => setActive(node.id)} onMouseLeave={() => setActive(null)} className="cursor-default">
              <rect x={node.x} y={node.y} width={layout.nodeWidth} height={node.height} rx={3} fill={seriesColor(node.column)} />
              <text x={node.x + layout.nodeWidth + 8} y={node.y + node.height / 2} dominantBaseline="middle" className="fill-fg text-[13px] font-semibold">
                {short(node.label)}
                <tspan className="fill-muted font-normal"> · {node.value}</tspan>
              </text>
              <title>{`${node.label}: ${posts(node.value)}`}</title>
            </g>
          ))}
        </g>
      </svg>
      <ul className="sr-only">
        {layout.links.map((link) => (
          <li key={`${link.source}>${link.target}`}>{`${label.get(link.source)} to ${label.get(link.target)}: ${posts(link.value)}`}</li>
        ))}
      </ul>
    </div>
  )
}
