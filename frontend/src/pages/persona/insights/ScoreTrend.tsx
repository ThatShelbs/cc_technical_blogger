import { useState } from 'react'
import { Link } from 'react-router'

import type { PostPoint } from '../../../api/types.gen'

type ScoreKey = 'voice_match' | 'authenticity'
const SERIES: { key: ScoreKey; label: string; color: string; dot: string }[] = [
  { key: 'voice_match', label: 'Voice match', color: 'var(--color-chart-1)', dot: 'bg-chart-1' },
  { key: 'authenticity', label: 'Reads as human', color: 'var(--color-chart-2)', dot: 'bg-chart-2' },
]
const W = 600
const H = 170
const PAD = { left: 30, right: 14, top: 10, bottom: 8 }
const score = (value: number | null | undefined) => (typeof value === 'number' ? Math.round(value) : '–')

/** Two 0-100 scores per post, oldest first, on one shared axis. */
export function ScoreTrend({ points }: { points: PostPoint[] }) {
  const [hover, setHover] = useState<number | null>(null)
  const recent = points.slice(-20)
  const x = (index: number) => (recent.length === 1 ? (PAD.left + W - PAD.right) / 2 : PAD.left + (index / (recent.length - 1)) * (W - PAD.left - PAD.right))
  const y = (value: number) => PAD.top + (1 - value / 100) * (H - PAD.top - PAD.bottom)
  const slot = recent.length > 1 ? (W - PAD.left - PAD.right) / (recent.length - 1) : W
  const shown = hover === null ? null : recent[hover]

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm">
        {SERIES.map((series) => (
          <span key={series.key} className="flex items-center gap-2">
            <span className={`size-3 rounded-full ${series.dot}`} aria-hidden />
            <span className="font-semibold">{series.label}</span>
          </span>
        ))}
        <span className="min-h-5 text-muted" aria-live="polite">
          {shown && `${shown.title}: voice match ${score(shown.voice_match)}, reads as human ${score(shown.authenticity)}`}
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Voice match and reads-as-human scores per post, oldest first">
        {[0, 50, 100].map((tick) => (
          <g key={tick}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(tick)} y2={y(tick)} className="stroke-line" strokeWidth={1} />
            <text x={PAD.left - 8} y={y(tick)} textAnchor="end" dominantBaseline="middle" className="fill-muted text-[11px]">
              {tick}
            </text>
          </g>
        ))}
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={H - PAD.bottom} className="stroke-muted" strokeWidth={1} strokeDasharray="3 3" />}
        {SERIES.map((series) => {
          const marks = recent
            .map((point, index) => ({ index, value: point[series.key] }))
            .filter((m): m is { index: number; value: number } => m.value !== null)
          return (
            <g key={series.key}>
              {marks.length > 1 && (
                <polyline
                  points={marks.map((m) => `${x(m.index)},${y(m.value)}`).join(' ')}
                  fill="none"
                  stroke={series.color}
                  strokeWidth={2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              )}
              {marks.map((m) => (
                <circle
                  key={m.index}
                  cx={x(m.index)}
                  cy={y(m.value)}
                  r={hover === m.index ? 6 : 4.5}
                  fill={series.color}
                  className="stroke-surface"
                  strokeWidth={2}
                />
              ))}
            </g>
          )
        })}
        {recent.map((point, index) => (
          <rect
            key={point.project_id}
            x={x(index) - slot / 2}
            y={0}
            width={slot}
            height={H}
            fill="transparent"
            onMouseEnter={() => setHover(index)}
            onMouseLeave={() => setHover(null)}
          >
            <title>{`${point.title}: voice match ${score(point.voice_match)}, reads as human ${score(point.authenticity)}`}</title>
          </rect>
        ))}
      </svg>
      <p className="mt-1 text-xs text-muted">Oldest post on the left. Both scores run from 0 to 100; higher is better.</p>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer font-semibold text-muted hover:text-fg">Show as a table</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-left">
            <thead className="text-xs text-muted">
              <tr>
                <th className="py-1 pr-3 font-semibold">Post</th>
                <th className="py-1 pr-3 text-right font-semibold">Words</th>
                <th className="py-1 pr-3 text-right font-semibold">Voice match</th>
                <th className="py-1 text-right font-semibold">Reads as human</th>
              </tr>
            </thead>
            <tbody>
              {[...recent].reverse().map((point) => (
                <tr key={point.project_id} className="border-t border-line">
                  <td className="py-1.5 pr-3">
                    <Link to={`/projects/${point.project_id}`} className="font-semibold hover:text-accent">
                      {point.title}
                    </Link>
                  </td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{point.words.toLocaleString()}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{score(point.voice_match)}</td>
                  <td className="py-1.5 text-right tabular-nums">{score(point.authenticity)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}
