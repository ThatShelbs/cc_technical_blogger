import type { Dials } from '../api/types.gen'

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

export interface DialsState {
  targetWords: number
  autoImages: boolean
  imageCount: number
  /** null = use the persona's default */
  humor: number | null
  /** null = use the persona's default */
  education: Education | null
  topic: string
  platform: 'medium' | 'substack' | 'gumroad' | 'markdown'
  includeCode: 'auto' | 'yes' | 'no'
}

/** Build the dials payload: only send what the user changed, so the backend's smart defaults apply. */
export function buildDials(custom: boolean, state: DialsState): Dials {
  if (!custom) return { platform: state.platform }
  const dials: Dials = { target_words: state.targetWords, platform: state.platform, include_code: state.includeCode }
  if (!state.autoImages) dials.image_count = state.imageCount
  if (state.humor !== null) dials.humor = state.humor
  if (state.education !== null) dials.education = state.education
  if (state.topic) dials.topic = state.topic
  return dials
}
