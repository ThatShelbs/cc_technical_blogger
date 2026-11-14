import type { CountItem } from '../../../api/types.gen'

/** Counts as horizontal bars on one shared scale, biggest first, each with its number. */
export function BarList({ items, unit }: { items: CountItem[]; unit: (count: number) => string }) {
  const max = Math.max(...items.map((i) => i.count), 1)
  return (
    <ul className="space-y-2.5">
      {items.map((item) => (
        <li key={item.id} title={`${item.label}: ${unit(item.count)}`} className="grid grid-cols-[minmax(0,10rem)_1fr_auto] items-center gap-3 text-sm">
          <span className="truncate">{item.label}</span>
          <span className="h-3 rounded-r-[4px] bg-chart-1" style={{ width: `${Math.max(2, (item.count / max) * 100)}%` }} aria-hidden />
          <span className="text-muted tabular-nums">{unit(item.count)}</span>
        </li>
      ))}
    </ul>
  )
}
