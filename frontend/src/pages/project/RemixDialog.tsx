import { Sparkles } from 'lucide-react'
import { useState } from 'react'

import type { ImageOut, RemixDimensionOut } from '../../api/types.gen'
import { Button, Dialog, Field, Select, Switch } from '../../components/ui'
import { remixSummary } from '../../lib/remix'

const SURPRISE = 'auto'

/**
 * Choose what the next redraw experiments with: colors, who is in it, staging and medium. Anything left on
 * "Surprise me" is picked for you, avoiding what the last redraws tried.
 */
export function RemixDialog({
  open,
  onClose,
  image,
  dimensions,
  onRemix,
}: {
  open: boolean
  onClose: () => void
  image: ImageOut
  /** The whole catalog; only the dimensions this image can vary are shown */
  dimensions: RemixDimensionOut[]
  onRemix: (tweaks: Record<string, string>, improve: boolean) => void
}) {
  const [picks, setPicks] = useState<Record<string, string>>({})
  const [improve, setImprove] = useState(true)
  const shown = dimensions.filter((d) => (image.remix_dimensions ?? []).includes(d.id))
  const last = remixSummary(image.remix)
  const pinned = Object.fromEntries(Object.entries(picks).filter(([, id]) => id && id !== SURPRISE))

  return (
    <Dialog open={open} onClose={onClose} title="Remix this image">
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          onRemix(pinned, improve)
        }}
      >
        <p className="text-sm text-muted">
          Claude redraws the same idea with an experiment. Pick what to try, or leave it on Surprise me. The current version stays in Versions.
        </p>
        {last && <p className="text-xs text-muted">Last redraw: {last}</p>}
        {shown.map((dimension) => {
          const id = `remix-${image.id}-${dimension.id}`
          const chosen = dimension.options.find((o) => o.id === picks[dimension.id])
          return (
            <Field key={dimension.id} label={dimension.label} htmlFor={id}>
              <div className="flex items-center gap-3">
                <Select id={id} value={picks[dimension.id] ?? SURPRISE} onChange={(e) => setPicks({ ...picks, [dimension.id]: e.target.value })}>
                  <option value={SURPRISE}>Surprise me</option>
                  {dimension.options.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </Select>
                {chosen && (chosen.swatch ?? []).length > 0 && (
                  <span aria-hidden className="flex shrink-0">
                    {(chosen.swatch ?? []).map((color) => (
                      <span key={color} className="size-4 first:rounded-l-full last:rounded-r-full" style={{ backgroundColor: color }} />
                    ))}
                  </span>
                )}
              </div>
            </Field>
          )
        })}
        <div className="flex items-center gap-3">
          <Switch checked={improve} onChange={setImprove} label="Critique first" />
          <span className="text-sm">Let Claude critique the current image first and fix its weakest point</span>
        </div>
        <Button type="submit" icon={<Sparkles className="size-4" />}>
          Remix
        </Button>
      </form>
    </Dialog>
  )
}
