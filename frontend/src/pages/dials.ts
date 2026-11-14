import type { Dials, FormulaParts, PersonaOut } from '../api/types.gen'
import { buildFormula, formulaFrom } from '../lib/formula'
import type { ReferenceKind } from '../lib/references'

export const TOPICS = [
  'Data Science',
  'Python Programming',
  'Data Visualization',
  'Machine Learning',
  'Causality, Experimentation & Causal Inference',
  'Leading Analytics & Data Science Teams',
  'Advanced Analytics at Large Companies',
  'AI, LLMs & Agents',
  'AI/ML Platforms (AWS, Snowflake)',
  'Building with Agentic Coding Tools',
]

export type Education = 'beginner' | 'intermediate' | 'expert'
export type Platform = 'medium' | 'substack' | 'linkedin' | 'x' | 'gumroad' | 'markdown'
export type IncludeCode = 'auto' | 'yes' | 'no'

export const PLATFORMS: [Platform, string][] = [
  ['medium', 'Medium'],
  ['substack', 'Substack'],
  ['linkedin', 'LinkedIn'],
  ['x', 'X (Article)'],
  ['gumroad', 'Gumroad'],
  ['markdown', 'Markdown (dev.to, Hashnode, Ghost)'],
]

/** 0-10 style dials. 5 = the author's natural level, so the voice profile stays in charge. */
export const STYLE_DIALS = [
  { key: 'storytelling', label: 'Storytelling', low: 'Straight explainer', high: 'Story-driven' },
  { key: 'opinion', label: 'Opinion strength', low: 'Balanced', high: 'Bold hot take' },
  { key: 'formality', label: 'Formality', low: 'Casual', high: 'Polished' },
  { key: 'technical_depth', label: 'Technical depth', low: 'Conceptual', high: 'Deep dive' },
  { key: 'skimmability', label: 'Skimmability', low: 'Flowing essay', high: 'Built for skimmers' },
] as const

export type StyleKey = (typeof STYLE_DIALS)[number]['key']

export function styleLabel(value: number, low: string, high: string): string {
  if (value <= 3) return `${value}/10 · ${low}`
  if (value >= 7) return `${value}/10 · ${high}`
  return `${value}/10 · As you write`
}

export interface DialsState {
  /** null = use the persona's default */
  targetWords: number | null
  /** null = use the persona's default (which may be automatic) */
  imageCount: number | null
  /** null = use the persona's default (which may be automatic); 0 = no references */
  referenceCount: number | null
  /** null = every kind */
  referenceKinds: ReferenceKind[] | null
  /** null = use the persona's default */
  humor: number | null
  /** null = use the persona's default */
  education: Education | null
  style: Partial<Record<StyleKey, number>>
  /** Only the formula parts changed for this post; the rest follow the persona's default formula */
  formula: FormulaParts
  topic: string
  /** Who the post is for; empty = the author's usual readers */
  audience: string
  /** null = use the persona's default */
  platform: Platform | null
  includeCode: IncludeCode | null
  /** null = use the persona's default; 'auto' = the panel picks across the styles that suit the post */
  openingStyle: string | null
  /** The author's own direction for the opening image; empty = none */
  openingNote: string
}

export const emptyDials: DialsState = {
  targetWords: null,
  imageCount: null,
  referenceCount: null,
  referenceKinds: null,
  humor: null,
  education: null,
  style: {},
  formula: {},
  topic: '',
  audience: '',
  platform: null,
  includeCode: null,
  openingStyle: null,
  openingNote: '',
}

/** Build the dials payload: only send what the user changed, so the persona's defaults and smart defaults apply. */
export function buildDials(state: DialsState): Dials {
  const dials: Dials = {}
  if (state.targetWords !== null) dials.target_words = state.targetWords
  if (state.imageCount !== null) dials.image_count = state.imageCount
  if (state.referenceCount !== null) dials.reference_count = state.referenceCount
  if (state.referenceKinds !== null) dials.reference_kinds = state.referenceKinds
  if (state.humor !== null) dials.humor = state.humor
  if (state.education !== null) dials.education = state.education
  for (const { key } of STYLE_DIALS) {
    const value = state.style[key]
    if (value !== undefined) dials[key] = value
  }
  if (state.topic) dials.topic = state.topic
  if (state.audience.trim()) dials.audience = state.audience.trim()
  if (state.platform !== null) dials.platform = state.platform
  if (state.includeCode !== null) dials.include_code = state.includeCode
  if (state.openingStyle !== null) dials.opening_style = state.openingStyle
  if (state.openingNote.trim()) dials.opening_note = state.openingNote.trim()
  return { ...dials, ...buildFormula(state.formula) }
}

/** The inverse of buildDials: a saved post's dials back into form state. */
export function dialsToState(dials: Dials | Record<string, unknown> | null | undefined): DialsState {
  const d = (dials ?? {}) as Dials
  const style: DialsState['style'] = {}
  for (const { key } of STYLE_DIALS) {
    const value = d[key]
    if (typeof value === 'number') style[key] = value
  }
  return {
    targetWords: d.target_words ?? null,
    imageCount: d.image_count ?? null,
    referenceCount: d.reference_count ?? null,
    referenceKinds: d.reference_kinds ?? null,
    humor: d.humor ?? null,
    education: d.education ?? null,
    style,
    formula: formulaFrom(d),
    topic: d.topic ?? '',
    audience: d.audience ?? '',
    platform: d.platform ?? null,
    includeCode: d.include_code ?? null,
    openingStyle: d.opening_style ?? null,
    openingNote: d.opening_note ?? '',
  }
}

/** The value a dial shows: the user's choice, else the persona default. */
export function personaStyle(persona: PersonaOut | undefined, key: StyleKey): number {
  return persona ? persona[`default_${key}`] : 5
}

export function autoImageCount(targetWords: number): number {
  return Math.max(2, Math.min(12, Math.round(targetWords / 350)))
}

/** What a dial shows: the user's choice, else the persona's default. */
export function shownDials(dials: DialsState, persona: PersonaOut | undefined) {
  const targetWords = dials.targetWords ?? persona?.default_target_words ?? 1500
  return {
    targetWords,
    imageCount: dials.imageCount ?? persona?.default_image_count ?? null,
    referenceCount: dials.referenceCount ?? persona?.default_reference_count ?? null,
    humor: dials.humor ?? persona?.default_humor ?? 5,
    education: dials.education ?? (persona?.default_education as Education | undefined) ?? 'intermediate',
    includeCode: dials.includeCode ?? (persona?.default_include_code as IncludeCode | undefined) ?? 'auto',
    openingStyle: dials.openingStyle ?? persona?.default_opening_style ?? 'auto',
  }
}
