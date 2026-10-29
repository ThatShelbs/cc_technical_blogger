import { Plus, X } from 'lucide-react'

import type { BrandKit } from '../api/types.gen'
import { MAX_BRAND_COLORS } from '../lib/brandKit'
import { Button, Field, Input } from './ui'

// A starting color for "Add color": the middle of the inferno palette.
const NEW_COLOR = '#cf4446'

/** The look of one post's images: style, palette, font and a recurring motif. Empty fields use the persona's visual style. */
export function BrandKitFields({
  kit,
  onChange,
  idPrefix = '',
  personaStyle,
}: {
  kit: Required<BrandKit>
  onChange: (kit: Required<BrandKit>) => void
  idPrefix?: string
  personaStyle?: string
}) {
  const id = (name: string) => `${idPrefix}brand-${name}`
  const setColor = (index: number, color: string) => onChange({ ...kit, palette: kit.palette.map((c, i) => (i === index ? color : c)) })
  return (
    <div className="space-y-4">
      <Field
        label="Image style"
        hint={personaStyle ? `Empty = the persona's style: ${personaStyle}` : 'Empty = the persona’s visual style.'}
        htmlFor={id('style')}
      >
        <Input
          id={id('style')}
          value={kit.style}
          maxLength={300}
          placeholder="Hand-drawn chalkboard sketches"
          onChange={(e) => onChange({ ...kit, style: e.target.value })}
        />
      </Field>
      <fieldset className="space-y-2">
        <legend className="text-sm font-semibold">Palette</legend>
        <p className="text-xs text-muted">Empty = the inferno palette.</p>
        <div className="flex flex-wrap items-center gap-2">
          {kit.palette.map((color, index) => (
            <span key={index} className="inline-flex items-center gap-1 rounded-lg border border-line p-1">
              <input
                type="color"
                value={color}
                aria-label={`Palette color ${index + 1}`}
                className="h-7 w-9 cursor-pointer rounded border-0 bg-transparent"
                onChange={(e) => setColor(index, e.target.value)}
              />
              <button
                type="button"
                className="rounded p-0.5 text-muted hover:text-danger"
                aria-label={`Remove color ${index + 1}`}
                onClick={() => onChange({ ...kit, palette: kit.palette.filter((_, i) => i !== index) })}
              >
                <X className="size-3.5" />
              </button>
            </span>
          ))}
          {kit.palette.length < MAX_BRAND_COLORS && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              icon={<Plus className="size-4" />}
              onClick={() => onChange({ ...kit, palette: [...kit.palette, NEW_COLOR] })}
            >
              Add color
            </Button>
          )}
        </div>
      </fieldset>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Font for text in images" htmlFor={id('font')}>
          <Input id={id('font')} value={kit.font} maxLength={80} placeholder="Georgia" onChange={(e) => onChange({ ...kit, font: e.target.value })} />
        </Field>
        <Field label="Recurring motif" htmlFor={id('motif')}>
          <Input
            id={id('motif')}
            value={kit.motif}
            maxLength={200}
            placeholder="A tiny robot in every image"
            onChange={(e) => onChange({ ...kit, motif: e.target.value })}
          />
        </Field>
      </div>
    </div>
  )
}
