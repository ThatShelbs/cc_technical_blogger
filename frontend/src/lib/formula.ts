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

/** A title signal alone is enough; outline bullets need three (mirrors DETECT_MIN in writer/formulas.py). */
const DETECT_MIN = 3

/**
 * The article type a brief asks for, if it says: the same rule the backend applies when the type is left automatic
 * (`detect_article_type` in writer/formulas.py), run here so the form can show the guess while the author types.
 */
export function detectArticleType(brief: string, catalog: FormulaCatalogOut): ArticleType | undefined {
  const [first = '', ...rest] = brief.trim().split('\n')
  const body = rest.join('\n')
  let best: ArticleType | undefined
  let bestScore = DETECT_MIN - 1
  for (const type of catalog.article_types) {
    let score = 0
    for (const signal of type.signals ?? []) {
      const pattern = new RegExp(signal, 'i')
      score += (pattern.test(first) ? 3 : 0) + (pattern.test(body) ? 1 : 0)
    }
    if (score > bestScore) {
      best = type
      bestScore = score
    }
  }
  return best
}

export interface ShuffleOptions {
  /** The article type in force (chosen or read from the brief); its suggested styles are the pool. */
  type?: ArticleType
  /** At humor 0-2 a shuffle never lands on a joke opener (the author can still pick one). */
  humor?: number
  rng?: () => number
}

/**
 * Another style for one part, drawn from the styles that suit the article type and never the current one.
 * With no article type, openers and closers come from the whole catalog and the body is left alone, because a
 * body structure only makes sense for the kind of post it was made for. Returns undefined when there is nothing to draw.
 */
export function shufflePart(part: Part, current: string, catalog: FormulaCatalogOut, { type, humor = 5, rng = Math.random }: ShuffleOptions = {}) {
  const { catalogKey } = PARTS.find((p) => p.part === part)!
  const all = catalog[catalogKey]
  let pool = type ? type[catalogKey].map((id) => all.find((o) => o.id === id)).filter((o): o is FormulaOption => !!o) : part === 'body' ? [] : all
  if (part === 'opener' && humor <= 2) pool = pool.filter((o) => o.group !== 'Joke')
  const fresh = pool.filter((o) => o.id !== current)
  const from = fresh.length ? fresh : pool
  return from.length ? from[Math.floor(rng() * from.length) % from.length].id : undefined
}

/** A new opener, body and closer in one go (the article type and the author's notes stay as they are). */
export function shuffleFormula(formula: ReturnType<typeof effective>, catalog: FormulaCatalogOut, options: ShuffleOptions = {}): FormulaParts {
  const out: FormulaParts = {}
  for (const { part } of PARTS) {
    const next = shufflePart(part, formula[part], catalog, options)
    if (next) out[part] = next
  }
  return out
}
