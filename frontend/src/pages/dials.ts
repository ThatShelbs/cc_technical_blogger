import type { Dials, PersonaOut } from '../api/types.gen'

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
export type Platform = 'medium' | 'substack' | 'linkedin' | 'gumroad' | 'markdown'
export type IncludeCode = 'auto' | 'yes' | 'no'

export const PLATFORMS: [Platform, string][] = [
  ['medium', 'Medium'],
  ['substack', 'Substack'],
  ['linkedin', 'LinkedIn'],
  ['gumroad', 'Gumroad'],
  ['markdown', 'Markdown (dev.to, Hashnode, Ghost)'],
]

/** 0-10 style dials. 5 = the author's natural level, so the voice soul stays in charge. */
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
  /** null = use the persona's default */
  humor: number | null
  /** null = use the persona's default */
  education: Education | null
  style: Partial<Record<StyleKey, number>>
  topic: string
  /** null = use the persona's default */
  platform: Platform | null
  includeCode: IncludeCode | null
}

export const emptyDials: DialsState = {
  targetWords: null,
  imageCount: null,
  humor: null,
  education: null,
  style: {},
  topic: '',
  platform: null,
  includeCode: null,
}

/** Build the dials payload: only send what the user changed, so the persona's defaults and smart defaults apply. */
export function buildDials(state: DialsState): Dials {
  const dials: Dials = {}
  if (state.targetWords !== null) dials.target_words = state.targetWords
  if (state.imageCount !== null) dials.image_count = state.imageCount
  if (state.humor !== null) dials.humor = state.humor
  if (state.education !== null) dials.education = state.education
  for (const { key } of STYLE_DIALS) {
    const value = state.style[key]
    if (value !== undefined) dials[key] = value
  }
  if (state.topic) dials.topic = state.topic
  if (state.platform !== null) dials.platform = state.platform
  if (state.includeCode !== null) dials.include_code = state.includeCode
  return dials
}

/** The value a dial shows: the user's choice, else the persona default. */
export function personaStyle(persona: PersonaOut | undefined, key: StyleKey): number {
  return persona ? persona[`default_${key}`] : 5
}

export function autoImageCount(targetWords: number): number {
  return Math.max(2, Math.min(12, Math.round(targetWords / 350)))
}
