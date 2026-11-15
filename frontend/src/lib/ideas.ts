import type { IdeaOut, IdeaTrendOut } from '../api/types.gen'

export type IdeaMode = 'light' | 'medium' | 'heavy'
export type IdeaSort = 'best' | 'theme' | 'source'
export type IdeaFilter = 'open' | 'saved' | 'used' | 'dismissed'

export const MODES: { id: IdeaMode; label: string; count: number; hint: string }[] = [
  { id: 'light', label: 'Light', count: 10, hint: 'A quick shortlist.' },
  { id: 'medium', label: 'Medium', count: 25, hint: 'A full spread across themes.' },
  { id: 'heavy', label: 'Heavy', count: 50, hint: 'Everything worth considering. Takes the longest.' },
]

export const SORTS: { id: IdeaSort; label: string }[] = [
  { id: 'best', label: 'AI suggestion' },
  { id: 'theme', label: 'Themes' },
  { id: 'source', label: 'Source approach' },
]

export const FILTERS: { id: IdeaFilter; label: string }[] = [
  { id: 'open', label: 'To consider' },
  { id: 'saved', label: 'Saved' },
  { id: 'used', label: 'Written' },
  { id: 'dismissed', label: 'Dismissed' },
]

/** Source approaches in display order, with what each one means. */
export const APPROACHES: { id: string; label: string; hint: string }[] = [
  { id: 'emerging', label: 'Live and Emerging', hint: 'From what is happening in the field right now.' },
  { id: 'builder', label: 'Portfolio Builder', hint: 'The next post for readers of your recent work.' },
  { id: 'expander', label: 'Portfolio Expander', hint: 'Ground you have not covered lately.' },
  { id: 'reader_questions', label: 'Reader Questions', hint: 'What practitioners keep asking.' },
  { id: 'counter_take', label: 'Counter-take', hint: 'Where you would push back on a popular claim.' },
  { id: 'sparks', label: 'Your Sparks', hint: 'Your own notes, developed into posts.' },
  { id: 'own', label: 'Your own idea', hint: 'Added by you to the saved bank.' },
]

export type IdeaStage = IdeaOut['stage']
type Tone = 'neutral' | 'accent' | 'success' | 'danger' | 'flame'

/** The idea lifecycle in order (mirrors `idealab/lifecycle.py`). The last four are a published post's outcome. */
export const STAGES: { id: IdeaStage; label: string; tone: Tone; hint: string }[] = [
  { id: 'prospective', label: 'Prospective', tone: 'neutral', hint: 'Fresh from a brainstorm.' },
  { id: 'serious', label: 'Serious', tone: 'accent', hint: 'Saved to the bank: you mean to write it.' },
  { id: 'generated', label: 'Generated', tone: 'accent', hint: 'Written as a post, still a draft.' },
  { id: 'ready', label: 'Ready', tone: 'accent', hint: 'The post is ready to publish.' },
  { id: 'published', label: 'Published', tone: 'success', hint: 'The post is out.' },
  { id: 'too_early', label: 'Too early', tone: 'success', hint: 'Published; no verdict yet.' },
  { id: 'small_hit', label: 'Small hit', tone: 'success', hint: 'Published: a few reads and reactions.' },
  { id: 'medium_hit', label: 'Medium hit', tone: 'success', hint: 'Published and did well.' },
  { id: 'big_hit', label: 'Big hit', tone: 'flame', hint: 'Published and took off.' },
  { id: 'dismissed', label: 'Dismissed', tone: 'neutral', hint: 'Passed on; never suggested again.' },
]

export const stageOf = (id: string) => STAGES.find((s) => s.id === id) ?? STAGES[0]

/** The main steps shown as a progress line; every outcome counts as the last step. */
export const LIFECYCLE_STEPS: { id: string; label: string }[] = [
  { id: 'prospective', label: 'Prospective' },
  { id: 'serious', label: 'Serious' },
  { id: 'generated', label: 'Generated' },
  { id: 'ready', label: 'Ready' },
  { id: 'published', label: 'Published' },
]

/** Index of the stage on the progress line (outcomes = published); -1 for dismissed. */
export function stepIndex(stage: IdeaStage): number {
  if (stage === 'dismissed') return -1
  const at = LIFECYCLE_STEPS.findIndex((s) => s.id === stage)
  return at === -1 ? LIFECYCLE_STEPS.length - 1 : at
}

export type BankFilter = 'serious' | 'in_progress' | 'published' | 'all' | 'dismissed'

const BANK_STAGES: Record<BankFilter, IdeaStage[] | null> = {
  serious: ['serious'],
  in_progress: ['generated', 'ready'],
  published: ['published', 'too_early', 'small_hit', 'medium_hit', 'big_hit'],
  all: null,
  dismissed: ['dismissed'],
}

export const BANK_FILTERS: { id: BankFilter; label: string }[] = [
  { id: 'serious', label: 'To write' },
  { id: 'in_progress', label: 'In progress' },
  { id: 'published', label: 'Published' },
  { id: 'all', label: 'All kept' },
  { id: 'dismissed', label: 'Dismissed' },
]

/** The bank in one view, searched by title, brief, note and theme. "All kept" leaves out dismissed ideas. */
export function filterBank(ideas: IdeaOut[], filter: BankFilter, search = ''): IdeaOut[] {
  const stages = BANK_STAGES[filter]
  const words = search.toLowerCase().split(/\s+/).filter(Boolean)
  return ideas.filter((idea) => {
    if (stages ? !stages.includes(idea.stage) : idea.stage === 'dismissed') return false
    const text = `${idea.title} ${idea.brief} ${idea.note} ${idea.theme}`.toLowerCase()
    return words.every((w) => text.includes(w))
  })
}

export const SHELF_LIFE: Record<string, string> = { this_week: 'Write this week', this_month: 'This month', evergreen: 'Evergreen' }

export const SCORES: { key: string; label: string; hint: string }[] = [
  { key: 'timeliness', label: 'Timeliness', hint: 'How much it matters to write this soon.' },
  { key: 'demand', label: 'Reader demand', hint: 'How many of your readers want this now.' },
  { key: 'fit', label: 'Fit with you', hint: 'How natural and credible it is for you.' },
  { key: 'differentiation', label: 'Differentiation', hint: 'How different the angle is from what is out there.' },
  { key: 'effort', label: 'Ease', hint: '10 = you could write it well this week.' },
]

export const TREND_KINDS: { id: string; label: string }[] = [
  { id: 'launch', label: 'Launches and announcements' },
  { id: 'claim', label: 'Claims and hot takes' },
  { id: 'industry_pattern', label: 'Industry patterns' },
  { id: 'creator_wave', label: 'What everyone is writing about' },
  { id: 'question', label: 'What practitioners are asking' },
]

export const scoreOf = (idea: IdeaOut, key: string): number => {
  const value = Number(idea.scores?.[key])
  return Number.isFinite(value) ? value : 0
}

export function filterIdeas(ideas: IdeaOut[], filter: IdeaFilter): IdeaOut[] {
  if (filter === 'open') return ideas.filter((i) => i.state === 'new' || i.state === 'saved')
  return ideas.filter((i) => i.state === filter)
}

export interface IdeaGroup {
  key: string
  label: string
  hint?: string
  ideas: IdeaOut[]
}

const byRank = (a: IdeaOut, b: IdeaOut) => a.rank - b.rank

/**
 * The board in one of its three orders. Ideas are always best first inside a group; theme groups are ordered by
 * their best idea, source groups in the fixed order of `APPROACHES`.
 */
export function groupIdeas(ideas: IdeaOut[], sort: IdeaSort): IdeaGroup[] {
  const ranked = [...ideas].sort(byRank)
  if (sort === 'best') return ranked.length ? [{ key: 'best', label: 'Best first', ideas: ranked }] : []
  const groups = new Map<string, IdeaGroup>()
  for (const idea of ranked) {
    const key = sort === 'theme' ? idea.theme || 'Other' : idea.approach
    const approach = APPROACHES.find((a) => a.id === idea.approach)
    const group = groups.get(key) ?? {
      key,
      label: sort === 'theme' ? key : (approach?.label ?? idea.approach_label),
      hint: sort === 'source' ? approach?.hint : undefined,
      ideas: [],
    }
    group.ideas.push(idea)
    groups.set(key, group)
  }
  const list = [...groups.values()]
  if (sort === 'source') {
    const order = (key: string) => {
      const index = APPROACHES.findIndex((a) => a.id === key)
      return index === -1 ? APPROACHES.length : index
    }
    return list.sort((a, b) => order(a.key) - order(b.key))
  }
  // Map insertion order is already "by best idea" because the ideas were ranked first.
  return list
}

export function groupTrends(trends: IdeaTrendOut[]): { id: string; label: string; trends: IdeaTrendOut[] }[] {
  return TREND_KINDS.map((kind) => ({
    ...kind,
    trends: trends.filter((t) => t.kind === kind.id).sort((a, b) => b.heat - a.heat),
  })).filter((group) => group.trends.length > 0)
}

/** A date from the API: stored dates are UTC, sent sometimes with a zone and sometimes without. */
export function parseDate(iso: string): Date {
  return new Date(/([zZ]|[+-]\d\d:\d\d)$/.test(iso) ? iso : `${iso}Z`)
}

/** "3 hours ago", "2 days ago"; empty when there is no date. */
export function ago(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return ''
  const then = parseDate(iso)
  const minutes = Math.max(0, Math.round((now.getTime() - then.getTime()) / 60000))
  if (minutes < 2) return 'just now'
  if (minutes < 60) return `${minutes} minutes ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.round(hours / 24)
  return `${days} day${days === 1 ? '' : 's'} ago`
}

/** One name per line or comma-separated, trimmed, without blanks or repeats. */
export function parseNames(text: string): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const raw of text.split(/[\n,]/)) {
    const name = raw.trim().replace(/\s+/g, ' ')
    if (name && !seen.has(name.toLowerCase())) {
      seen.add(name.toLowerCase())
      out.push(name)
    }
  }
  return out
}
