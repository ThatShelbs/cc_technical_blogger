import type { ArticleType, FormulaCatalogOut, FormulaOption, FormulaOut, FormulaParts } from '../api/types.gen'

/** "The author's usual way": the voice profile decides. */
export const AUTO = 'auto'

export type Part = 'opener' | 'body' | 'closer'
export type Choice = 'article_type' | Part
export type Note = `${Part}_note`

export const PARTS: { part: Part; label: string; catalogKey: 'openers' | 'bodies' | 'closers'; auto: string; notePlaceholder: string }[] = [
  { part: 'opener', label: 'Opener', catalogKey: 'openers', auto: 'As you usually open', notePlaceholder: 'Start with the 3 a.m. pager alert' },
  { part: 'body', label: 'Body', catalogKey: 'bodies', auto: 'As you usually structure it', notePlaceholder: 'Three sections, each ending on a rule of thumb' },
  { part: 'closer', label: 'Closer', catalogKey: 'closers', auto: 'As you usually end', notePlaceholder: 'End by asking which chart they would retire' },
]

const CHOICES: Choice[] = ['article_type', 'opener', 'body', 'closer']
const NOTES: Note[] = ['opener_note', 'body_note', 'closer_note']

export const EMPTY_CATALOG: FormulaCatalogOut = { article_types: [], openers: [], bodies: [], closers: [] }

/** What a control shows: the post's own choice, else the persona's default, else automatic. */
export function shownChoice(value: FormulaParts, defaults: FormulaParts | undefined, field: Choice): string {
  return value[field] ?? defaults?.[field] ?? AUTO
}

export function shownNote(value: FormulaParts, defaults: FormulaParts | undefined, field: Note): string {
  return value[field] ?? defaults?.[field] ?? ''
}

/**
 * The patch for picking `next`: nothing is stored when it equals what the persona's default already gives,
 * so an untouched formula keeps following the persona.
 */
export function pickChoice(defaults: FormulaParts | undefined, field: Choice, next: string): FormulaParts {
  return { [field]: next === (defaults?.[field] ?? AUTO) ? null : next }
}

export function pickNote(defaults: FormulaParts | undefined, field: Note, next: string): FormulaParts {
  return { [field]: next === (defaults?.[field] ?? '') ? null : next }
}

/** Only what was set, ready for a dials or persona payload. */
export function buildFormula(value: FormulaParts): FormulaParts {
  const out: FormulaParts = {}
  for (const field of CHOICES) if (value[field]) out[field] = value[field]
  for (const field of NOTES) if (typeof value[field] === 'string') out[field] = value[field]
  return out
}

/** The formula fields of a saved post's dials (or a persona's default). */
export function formulaFrom(source: FormulaParts | Record<string, unknown> | null | undefined): FormulaParts {
  const out: FormulaParts = {}
  const from = (source ?? {}) as Record<string, unknown>
  for (const field of [...CHOICES, ...NOTES]) if (typeof from[field] === 'string') out[field] = from[field] as string
  return out
}

/** A saved formula as a full choice: every part is explicit, so it also overrides the persona's default. */
export function applySaved(saved: FormulaOut): FormulaParts {
  return {
    article_type: saved.article_type,
    opener: saved.opener,
    body: saved.body,
    closer: saved.closer,
    opener_note: saved.opener_note,
    body_note: saved.body_note,
    closer_note: saved.closer_note,
  }
}

/** The effective formula (what would be written with), for saving under a name or comparing with a saved one. */
export function effective(value: FormulaParts, defaults?: FormulaParts): Required<{ [K in Choice | Note]: string }> {
  return {
    article_type: shownChoice(value, defaults, 'article_type'),
    opener: shownChoice(value, defaults, 'opener'),
    body: shownChoice(value, defaults, 'body'),
    closer: shownChoice(value, defaults, 'closer'),
    opener_note: shownNote(value, defaults, 'opener_note').trim(),
    body_note: shownNote(value, defaults, 'body_note').trim(),
    closer_note: shownNote(value, defaults, 'closer_note').trim(),
  }
}

export function isAutomatic(formula: ReturnType<typeof effective>): boolean {
  return CHOICES.every((f) => formula[f] === AUTO) && NOTES.every((f) => !formula[f])
}

export function matchesSaved(formula: ReturnType<typeof effective>, saved: FormulaOut): boolean {
  return [...CHOICES, ...NOTES].every((f) => formula[f] === saved[f])
}

/** The article type's classic formula: its first suggestion for each part. */
export function classicFormula(type: ArticleType): FormulaParts {
  return { opener: type.openers[0] ?? AUTO, body: type.bodies[0] ?? AUTO, closer: type.closers[0] ?? AUTO }
}

export interface OptionGroup {
  label: string
  options: FormulaOption[]
}

/** Options for one part's menu: the styles that suit the article type first (best first), then the rest by family. */
export function groupOptions(options: FormulaOption[], suggested: string[] | undefined, typeLabel?: string): OptionGroup[] {
  const groups: OptionGroup[] = []
  const fit = (suggested ?? []).map((id) => options.find((o) => o.id === id)).filter((o): o is FormulaOption => !!o)
  if (fit.length) groups.push({ label: `Good fit for ${typeLabel ?? 'this type'}`, options: fit })
  for (const option of options) {
    if (fit.includes(option)) continue
    const group = groups.find((g) => g.label === option.group)
    if (group) group.options.push(option)
    else groups.push({ label: option.group, options: [option] })
  }
  return groups
}
