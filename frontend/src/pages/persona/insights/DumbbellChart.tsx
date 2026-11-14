import type { FingerprintOut } from '../../../api/types.gen'
import { formatNumber, niceMax } from '../../../lib/charts'

/** Rows that live on a fixed 0-100 scale; every other row gets its own scale from its two values. */
const fixedScale = (unit: string) => unit.startsWith('%') || unit.startsWith('0-100')

/** The style fingerprint: the author against a reference, one row and one scale per measure. */
export function DumbbellChart({ fingerprint }: { fingerprint: FingerprintOut }) {
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-x-5 gap-y-1 text-sm">
        <span className="flex items-center gap-2">
          <span className="size-3 rounded-full bg-chart-2" aria-hidden />
          <span className="font-semibold">You</span>
        </span>
        <span className="flex items-center gap-2">
          <span className="size-3 rounded-full border-2 border-muted bg-surface" aria-hidden />
          <span className="text-muted">{fingerprint.reference_label}</span>
        </span>
      </div>
      <ul className="divide-y divide-line">
        {fingerprint.rows.map((row) => {
          const max = fixedScale(row.unit) ? 100 : niceMax(Math.max(row.you, row.reference ?? 0) * 1.1)
          const at = (value: number) => `${Math.min(100, Math.max(0, (value / max) * 100))}%`
          const suffix = row.unit.startsWith('%') ? '%' : ''
          const [low, high] = row.reference === null ? [row.you, row.you] : [Math.min(row.you, row.reference), Math.max(row.you, row.reference)]
          const title = `${row.label}: you ${formatNumber(row.you)}${suffix}${
            row.reference === null ? '' : `, ${fingerprint.reference_label.toLowerCase()} ${formatNumber(row.reference)}${suffix}`
          } (${row.unit})`
          return (
            <li key={row.key} title={title} className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 py-2.5 sm:grid-cols-[11rem_1fr_7.5rem]">
              <div className="min-w-0">
                <p className="text-sm font-semibold">{row.label}</p>
                <p className="text-xs text-muted">{row.unit}</p>
              </div>
              <p className="text-right text-sm tabular-nums sm:order-3">
                <span className="font-bold">
                  {formatNumber(row.you)}
                  {suffix}
                </span>
                {row.reference !== null && (
                  <span className="text-muted">
                    {' '}
                    vs {formatNumber(row.reference)}
                    {suffix}
                  </span>
                )}
              </p>
              <div className="relative col-span-2 mx-2 h-5 sm:col-span-1" aria-hidden>
                <span className="absolute inset-x-0 top-1/2 h-px bg-line" />
                <span className="absolute top-1/2 h-0.5 -translate-y-1/2 bg-muted/50" style={{ left: at(low), right: `calc(100% - ${at(high)})` }} />
                {row.reference !== null && (
                  <span
                    className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-muted bg-surface"
                    style={{ left: at(row.reference) }}
                  />
                )}
                <span
                  className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-chart-2 ring-2 ring-surface"
                  style={{ left: at(row.you) }}
                />
              </div>
            </li>
          )
        })}
      </ul>
      <p className="mt-2 text-xs text-muted">Each row has its own scale, starting at zero.</p>
    </div>
  )
}
