import { useState } from 'react'

import type { VoiceMixSlice } from '../../../api/types.gen'
import { cx } from '../../../lib/cx'
import { seriesColor, waffleCells } from '../../../lib/charts'

const SQUARES = 50

/** The voice mix: 50 squares, each 2% of the sentences Claude labeled, coloured by kind of sentence. */
export function WaffleChart({ slices }: { slices: VoiceMixSlice[] }) {
  const [active, setActive] = useState<number | null>(null)
  const cells = waffleCells(
    slices.map((s) => s.count),
    SQUARES,
  )
  const summary = slices.map((s) => `${s.name} ${Math.round(s.share)}%`).join(', ')
  return (
    <div className="flex flex-wrap items-start gap-x-6 gap-y-4">
      <div role="img" aria-label={`Voice mix: ${summary}`} className="grid w-full max-w-72 min-w-48 flex-1 grid-cols-10 gap-1">
        {cells.map((slice, index) => (
          <span
            key={index}
            title={`${slices[slice].name}: ${Math.round(slices[slice].share)}% (${slices[slice].count} sentences)`}
            onMouseEnter={() => setActive(slice)}
            onMouseLeave={() => setActive(null)}
            className={cx('aspect-square rounded-[4px] transition-opacity', active !== null && active !== slice && 'opacity-25')}
            style={{ backgroundColor: seriesColor(slice) }}
          />
        ))}
      </div>
      <ul className="space-y-1.5 text-sm">
        {slices.map((slice, index) => (
          <li
            key={slice.name}
            title={slice.description}
            onMouseEnter={() => setActive(index)}
            onMouseLeave={() => setActive(null)}
            className={cx('flex items-center gap-2 transition-opacity', active !== null && active !== index && 'opacity-40')}
          >
            <span className="size-3 shrink-0 rounded-[3px]" style={{ backgroundColor: seriesColor(index) }} aria-hidden />
            <span className="font-semibold">{slice.name}</span>
            <span className="text-muted tabular-nums">{Math.round(slice.share)}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
