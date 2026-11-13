import { ChevronDown, Dices, Save, Sparkles, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { errorText } from '../api/client'
import { useFormulaCatalog, useFormulaMutations, useFormulas } from '../api/hooks'
import type { FormulaParts } from '../api/types.gen'
import {
  AUTO,
  PARTS,
  applySaved,
  classicFormula,
  detectArticleType,
  effective,
  groupOptions,
  isAutomatic,
  matchesSaved,
  pickChoice,
  pickNote,
  shownNote,
  shuffleFormula,
  shufflePart,
  type Part,
} from '../lib/formula'
import { Button, Field, Input, Notice, Select } from './ui'

/**
 * The post's formula: article type, opener, body and closer, each a style from the catalog, the author's own
 * instructions, or both. `value` holds only what was changed here; `defaults` is the persona's default formula.
 * With the article type left automatic it is read from `brief`, as the backend will when it writes the post.
 */
export function FormulaFields({
  value,
  onChange,
  defaults,
  brief = '',
  humor,
  idPrefix = '',
}: {
  value: FormulaParts
  onChange: (patch: FormulaParts) => void
  defaults?: FormulaParts
  /** The post's brief, for the automatic article type */
  brief?: string
  /** The humor level in force, so a shuffle skips joke openers on a serious post */
  humor?: number
  idPrefix?: string
}) {
  const { data: catalog } = useFormulaCatalog()
  const { data: saved } = useFormulas()
  const { create, update, remove } = useFormulaMutations()
  const formula = effective(value, defaults)
  // Open whenever a part is set (the persona's defaults may load after the first render), until the author toggles it.
  const [toggled, setToggled] = useState<boolean | null>(null)
  const open = toggled ?? PARTS.some(({ part }) => formula[part] !== AUTO || !!formula[`${part}_note`])
  const setOpen = (next: boolean) => setToggled(next)
  const [naming, setNaming] = useState<string | null>(null)

  const id = (name: string) => `${idPrefix}formula-${name}`
  const chosenType = catalog.article_types.find((t) => t.id === formula.article_type)
  const detected = chosenType ? undefined : detectArticleType(brief, catalog)
  // The article type in force: chosen here or by the persona, else read from the brief.
  const type = chosenType ?? detected
  const pick = (patch: FormulaParts) =>
    onChange(Object.assign({}, ...(Object.entries(patch) as [Part, string][]).map(([part, next]) => pickChoice(defaults, part, next))))
  const shuffle = () => {
    pick(shuffleFormula(formula, catalog, { type, humor }))
    setOpen(true)
  }
  const current = saved.find((f) => matchesSaved(formula, f))
  const error = create.error ?? update.error ?? remove.error

  const save = () => {
    const name = (naming ?? '').trim()
    if (!name) return
    const existing = saved.find((f) => f.name.toLowerCase() === name.toLowerCase())
    const done = { onSuccess: () => setNaming(null) }
    if (existing) update.mutate({ id: existing.id, body: { ...formula, name: existing.name, description: existing.description } }, done)
    else create.mutate({ ...formula, name }, done)
  }

  return (
    <div className="space-y-4">
      {saved.length > 0 && (
        <Field label="Saved formula" htmlFor={id('saved')}>
          <div className="flex gap-2">
            <Select
              id={id('saved')}
              value={current?.id ?? ''}
              onChange={(e) => {
                const pick = saved.find((f) => f.id === Number(e.target.value))
                if (pick) {
                  onChange(applySaved(pick))
                  setOpen(true)
                }
              }}
            >
              <option value="">{isAutomatic(formula) ? 'Choose one…' : 'Custom (not saved)'}</option>
              {saved.map((f) => (
                <option key={f.id} value={f.id} title={f.label}>
                  {f.name}
                </option>
              ))}
            </Select>
            {current && (
              <button
                type="button"
                className="rounded-md p-2 text-muted hover:bg-danger-soft hover:text-danger"
                aria-label={`Delete saved formula ${current.name}`}
                onClick={() => confirm(`Delete the saved formula “${current.name}”? Posts written with it are not affected.`) && remove.mutate(current.id)}
              >
                <Trash2 className="size-4" />
              </button>
            )}
          </div>
        </Field>
      )}

      <Field
        label="Article type"
        hint={
          detected
            ? `Read from your brief. ${detected.summary}`
            : chosenType
              ? chosenType.summary
              : 'Read from your brief when it says; otherwise the shape you usually give a post.'
        }
        htmlFor={id('type')}
      >
        <Select id={id('type')} value={formula.article_type} onChange={(e) => onChange(pickChoice(defaults, 'article_type', e.target.value))}>
          <option value={AUTO}>{detected ? `Automatic: ${detected.label}` : 'Automatic (from your brief)'}</option>
          {catalog.article_types.map((t) => (
            <option key={t.id} value={t.id}>
              {t.label}
            </option>
          ))}
        </Select>
      </Field>

      <Button
        type="button"
        size="sm"
        variant="secondary"
        icon={<Dices className="size-4" />}
        title={type ? `A new opener, body and closer that suit ${type.label}` : 'A new opener and closer'}
        onClick={shuffle}
      >
        Shuffle the formula
      </Button>

      <button type="button" className="flex w-full items-center justify-between text-sm font-semibold" aria-expanded={open} onClick={() => setOpen(!open)}>
        Build the formula: opener, body, closer
        <ChevronDown className={`size-4 transition ${open ? 'rotate-180' : ''}`} aria-hidden />
      </button>

      {open && (
        <div className="space-y-4">
          {type && (
            <Button
              type="button"
              size="sm"
              variant="secondary"
              icon={<Sparkles className="size-4" />}
              onClick={() => {
                const classic = classicFormula(type)
                pick({ opener: classic.opener ?? AUTO, body: classic.body ?? AUTO, closer: classic.closer ?? AUTO })
              }}
            >
              Use the classic {type.label.split(' / ')[0].toLowerCase()} formula
            </Button>
          )}
          {PARTS.map(({ part, label, catalogKey, auto, notePlaceholder }) => {
            const options = catalog[catalogKey]
            const chosen = options.find((o) => o.id === formula[part])
            const suggested = type?.[catalogKey]
            return (
              <fieldset key={part} className="space-y-1.5">
                <legend className="sr-only">{label}</legend>
                <Field
                  label={label}
                  hint={
                    chosen ? chosen.summary : part === 'closer' ? 'The last lines of text. The closing meme always follows it.' : 'Left to your voice profile.'
                  }
                  htmlFor={id(part)}
                >
                  <div className="flex gap-2">
                    <Select id={id(part)} value={formula[part]} onChange={(e) => onChange(pickChoice(defaults, part, e.target.value))}>
                      <option value={AUTO}>{auto}</option>
                      {groupOptions(options, suggested, type?.label).map((group) => (
                        <optgroup key={group.label} label={group.label}>
                          {group.options.map((o) => (
                            <option key={o.id} value={o.id} title={o.summary}>
                              {o.label}
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </Select>
                    <button
                      type="button"
                      className="rounded-md p-2 text-muted hover:bg-surface-2 hover:text-fg disabled:opacity-40"
                      aria-label={`Shuffle the ${part}`}
                      title={`Another ${part}`}
                      disabled={!shufflePart(part, formula[part], catalog, { type, humor })}
                      onClick={() => {
                        const next = shufflePart(part, formula[part], catalog, { type, humor })
                        if (next) pick({ [part]: next })
                      }}
                    >
                      <Dices className="size-4" />
                    </button>
                  </div>
                </Field>
                <Input
                  aria-label={`Your own instructions for the ${part}`}
                  value={shownNote(value, defaults, `${part}_note`)}
                  maxLength={400}
                  placeholder="Add your own instructions"
                  title={`Optional, e.g. “${notePlaceholder}”`}
                  onChange={(e) => onChange(pickNote(defaults, `${part}_note`, e.target.value))}
                />
              </fieldset>
            )
          })}

          {naming === null ? (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              icon={<Save className="size-4" />}
              disabled={isAutomatic(formula) || !!current}
              onClick={() => setNaming('')}
            >
              {current ? `Saved as “${current.name}”` : 'Save as a formula'}
            </Button>
          ) : (
            <div className="space-y-1.5">
              <div className="flex gap-2">
                <Input
                  aria-label="Formula name"
                  autoFocus
                  value={naming}
                  maxLength={80}
                  placeholder="Name it, e.g. War story"
                  onChange={(e) => setNaming(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      save()
                    }
                    if (e.key === 'Escape') setNaming(null)
                  }}
                />
                <Button type="button" size="sm" disabled={!naming.trim()} loading={create.isPending || update.isPending} onClick={save}>
                  {saved.some((f) => f.name.toLowerCase() === naming.trim().toLowerCase()) ? 'Replace' : 'Save'}
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => setNaming(null)}>
                  Cancel
                </Button>
              </div>
              <p className="text-xs text-muted">Saved formulas can be reused on any post and with any persona.</p>
            </div>
          )}
          {error && <Notice tone="error">{errorText(error)}</Notice>}
        </div>
      )}
      {!open && shownSummary(formula, value, defaults) && <p className="text-xs text-muted">{shownSummary(formula, value, defaults)}</p>}
    </div>
  )
}

/** One line under the collapsed builder, so a set formula is never hidden. */
function shownSummary(formula: ReturnType<typeof effective>, value: FormulaParts, defaults?: FormulaParts): string {
  const set = PARTS.filter(({ part }) => formula[part] !== AUTO || formula[`${part}_note`]).map(({ label }) => label.toLowerCase())
  if (!set.length) return ''
  const own = PARTS.some(({ part }) => value[part] != null || value[`${part}_note`] != null)
  return `Set: ${set.join(', ')}${own || !defaults ? '' : ' (from the persona’s defaults)'}.`
}
