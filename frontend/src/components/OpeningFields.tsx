import { useFormulaCatalog, useOpeningStyles } from '../api/hooks'
import type { FormulaParts } from '../api/types.gen'
import { AUTO, detectArticleType, effective } from '../lib/formula'
import { openingHint } from '../lib/opening'
import { Field, Input, Select } from './ui'

/**
 * How the post opens: a style from the opening catalog, or Auto (the panel pitches across the styles that suit the
 * post and picks the most clickable idea). The hint names the styles that suit the article type in force, read from
 * the formula or, when that is automatic, from the brief, as the backend will.
 */
export function OpeningFields({
  style,
  note,
  onChange,
  defaultStyle,
  formula,
  formulaDefaults,
  brief = '',
  humor,
  idPrefix = '',
}: {
  /** null = the persona's default */
  style: string | null
  note: string
  onChange: (patch: { openingStyle?: string | null; openingNote?: string }) => void
  defaultStyle?: string
  formula: FormulaParts
  formulaDefaults?: FormulaParts
  brief?: string
  humor: number
  idPrefix?: string
}) {
  const { data: catalog } = useOpeningStyles()
  const { data: formulas } = useFormulaCatalog()
  const id = (name: string) => `${idPrefix}opening-${name}`
  const shown = style ?? defaultStyle ?? AUTO
  const chosenType = effective(formula, formulaDefaults).article_type
  const articleType = chosenType !== AUTO ? chosenType : (detectArticleType(brief, formulas)?.id ?? AUTO)
  const suits = catalog.suggested_by_type[articleType] ?? catalog.suggested_by_type[AUTO] ?? []
  const current = catalog.styles.find((s) => s.id === shown)
  return (
    <div className="space-y-3">
      <Field label="Style" htmlFor={id('style')}>
        <Select id={id('style')} value={shown} onChange={(e) => onChange({ openingStyle: e.target.value })}>
          <option value={AUTO}>Auto: the panel picks</option>
          {catalog.styles.map((s) => (
            <option key={s.id} value={s.id} disabled={humor < s.min_humor && s.id !== shown}>
              {s.label}
              {suits.includes(s.id) && s.id !== 'editorial' && s.id !== 'data_art' ? ' · suits this post' : ''}
              {humor < s.min_humor ? ` · needs humor ${s.min_humor}+` : ''}
            </option>
          ))}
        </Select>
      </Field>
      <p className="text-sm text-muted" aria-live="polite">
        {current ? current.summary : openingHint(suits, catalog.styles)}
        {current?.needs_data && ' Every number is researched and its source printed; if none can be verified, the next best idea is used.'}
      </p>
      <Field label="Your idea for it" hint="Optional. A metaphor, a number or a joke you want the room to consider." htmlFor={id('note')}>
        <Input
          id={id('note')}
          value={note}
          maxLength={400}
          onChange={(e) => onChange({ openingNote: e.target.value })}
          placeholder="Coins dropping through a plinko board into the marketing channels"
        />
      </Field>
    </div>
  )
}
