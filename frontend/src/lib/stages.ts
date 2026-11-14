/** Where a post is (draft, ready, published) and how a published post did. Mirrors `evolution/service.py`. */

export type Stage = 'draft' | 'ready' | 'published'
export type Outcome = 'too_early' | 'small' | 'good' | 'viral'
export type Tone = 'neutral' | 'accent' | 'success' | 'danger' | 'flame'

export const STAGES: { id: Stage; label: string; tone: Tone }[] = [
  { id: 'draft', label: 'Draft', tone: 'neutral' },
  { id: 'ready', label: 'Ready', tone: 'accent' },
  { id: 'published', label: 'Published', tone: 'success' },
]

export const OUTCOMES: { id: Outcome; label: string; tone: Tone; hint: string }[] = [
  { id: 'too_early', label: 'Too early', tone: 'neutral', hint: 'Just went out; no verdict yet.' },
  { id: 'small', label: 'Small traction', tone: 'neutral', hint: 'A few reads and reactions.' },
  { id: 'good', label: 'Good traction', tone: 'success', hint: 'Did well: learn what made it work.' },
  { id: 'viral', label: 'Viral', tone: 'flame', hint: 'A hit: learn what made it work.' },
]

/** Outcomes that are read for their secret sauce. */
export const SAUCE_OUTCOMES: Outcome[] = ['good', 'viral']

/** What a persona proposal was learned from, and where each change goes. */
export const KIND_LABEL: Record<string, string> = {
  edits: 'From your edits',
  secret_sauce: 'Secret sauce',
  ab_test: 'A/B test winner',
}

export const TARGET_LABEL: Record<string, string> = {
  profile: 'Voice profile',
  playbook: 'Playbook',
}

export const stageInfo = (id: string) => STAGES.find((s) => s.id === id) ?? STAGES[0]
export const outcomeInfo = (id: string | null | undefined) => OUTCOMES.find((o) => o.id === id)

export const percent = (rate: number) => `${Math.round(rate * 100)}%`
