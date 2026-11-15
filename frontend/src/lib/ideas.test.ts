import { describe, expect, it } from 'vitest'

import type { IdeaOut, IdeaTrendOut } from '../api/types.gen'
import { ago, filterBank, filterIdeas, groupIdeas, groupTrends, parseDate, parseNames, scoreOf, stageOf, stepIndex } from './ideas'

const idea = (rank: number, approach: string, theme: string, state: IdeaOut['state'] = 'new'): IdeaOut => ({
  id: rank,
  session_id: 1,
  persona_id: 1,
  approach,
  approach_label: approach,
  theme,
  title: `Idea ${rank}`,
  brief: '',
  angle: '',
  outline: [],
  why_now: '',
  shelf_life: 'evergreen',
  tags: [],
  evidence: [],
  article_type: 'auto',
  builds_on: '',
  scores: { fit: 7, note: 'ok' },
  score: 10 - rank,
  rank,
  state,
  stage: state === 'new' ? 'prospective' : state === 'saved' ? 'serious' : state === 'used' ? 'generated' : 'dismissed',
  stage_label: '',
  project_id: null,
  note: '',
  prompt: '',
  created_at: '2026-11-15T00:00:00',
})

const IDEAS = [
  idea(3, 'emerging', 'Agents'),
  idea(1, 'expander', 'Leadership'),
  idea(2, 'emerging', 'Agents', 'saved'),
  idea(4, 'builder', 'Leadership', 'dismissed'),
  idea(5, 'mystery', '', 'used'),
]

describe('groupIdeas', () => {
  it('lists the best idea first as one group', () => {
    const groups = groupIdeas(IDEAS, 'best')
    expect(groups).toHaveLength(1)
    expect(groups[0].ideas.map((i) => i.rank)).toEqual([1, 2, 3, 4, 5])
    expect(groupIdeas([], 'best')).toEqual([])
  })

  it('groups by theme, each theme placed by its best idea and ranked inside', () => {
    const groups = groupIdeas(IDEAS, 'theme')
    expect(groups.map((g) => g.label)).toEqual(['Leadership', 'Agents', 'Other'])
    expect(groups[0].ideas.map((i) => i.rank)).toEqual([1, 4])
    expect(groups[1].ideas.map((i) => i.rank)).toEqual([2, 3])
  })

  it('groups by source approach in the fixed order, unknown approaches last', () => {
    const groups = groupIdeas(IDEAS, 'source')
    expect(groups.map((g) => g.key)).toEqual(['emerging', 'builder', 'expander', 'mystery'])
    expect(groups[0].label).toBe('Live and Emerging')
    expect(groups[0].hint).toBeTruthy()
    expect(groups[0].ideas.map((i) => i.rank)).toEqual([2, 3])
  })
})

describe('filterIdeas', () => {
  it('keeps new and saved ideas in the open list', () => {
    expect(filterIdeas(IDEAS, 'open').map((i) => i.rank)).toEqual([3, 1, 2])
    expect(filterIdeas(IDEAS, 'saved').map((i) => i.rank)).toEqual([2])
    expect(filterIdeas(IDEAS, 'used').map((i) => i.rank)).toEqual([5])
    expect(filterIdeas(IDEAS, 'dismissed').map((i) => i.rank)).toEqual([4])
  })
})

describe('lifecycle', () => {
  it('places each stage on the progress line, outcomes on the last step', () => {
    expect(stepIndex('prospective')).toBe(0)
    expect(stepIndex('serious')).toBe(1)
    expect(stepIndex('ready')).toBe(3)
    expect(stepIndex('published')).toBe(4)
    expect(stepIndex('big_hit')).toBe(4)
    expect(stepIndex('dismissed')).toBe(-1)
    expect(stageOf('small_hit').label).toBe('Small hit')
  })

  it('filters and searches the bank', () => {
    const bank = [
      { ...idea(1, 'own', 'Agents', 'saved'), note: 'ask Sam' },
      { ...idea(2, 'emerging', 'Agents', 'used'), stage: 'ready' as const },
      { ...idea(3, 'emerging', 'Agents', 'used'), stage: 'big_hit' as const },
      idea(4, 'emerging', 'Agents', 'dismissed'),
    ]
    const ids = (filter: Parameters<typeof filterBank>[1], search = '') => filterBank(bank, filter, search).map((i) => i.id)
    expect(ids('serious')).toEqual([1])
    expect(ids('in_progress')).toEqual([2])
    expect(ids('published')).toEqual([3])
    expect(ids('all')).toEqual([1, 2, 3])
    expect(ids('dismissed')).toEqual([4])
    expect(ids('all', 'SAM')).toEqual([1])
    expect(ids('all', 'idea 3')).toEqual([3])
  })
})

describe('helpers', () => {
  it('reads scores as numbers', () => {
    expect(scoreOf(IDEAS[0], 'fit')).toBe(7)
    expect(scoreOf(IDEAS[0], 'note')).toBe(0)
    expect(scoreOf(IDEAS[0], 'missing')).toBe(0)
  })

  it('groups trends by kind, hottest first, leaving out empty kinds', () => {
    const trend = (id: number, kind: string, heat: number) => ({ id, kind, heat }) as IdeaTrendOut
    const groups = groupTrends([trend(1, 'claim', 4), trend(2, 'launch', 5), trend(3, 'launch', 9)])
    expect(groups.map((g) => g.id)).toEqual(['launch', 'claim'])
    expect(groups[0].trends.map((t) => t.id)).toEqual([3, 2])
  })

  it('says how long ago, treating stored dates as UTC', () => {
    const now = new Date('2026-11-15T12:00:00Z')
    expect(ago('2026-11-15T11:59:30', now)).toBe('just now')
    expect(ago('2026-11-15T11:15:00+00:00', now)).toBe('45 minutes ago')
    expect(ago('2026-11-15T09:00:00', now)).toBe('3 hours ago')
    expect(ago('2026-11-13T12:00:00Z', now)).toBe('2 days ago')
    expect(ago(null, now)).toBe('')
    expect(parseDate('2026-11-15T09:00:00.123456+00:00').toISOString()).toBe('2026-11-15T09:00:00.123Z')
    expect(parseDate('2026-11-15T09:00:00.123456').toISOString()).toBe('2026-11-15T09:00:00.123Z')
  })

  it('parses a list of names', () => {
    expect(parseNames(' Ada  Lovelace \nGrace Hopper, ada lovelace\n\n')).toEqual(['Ada Lovelace', 'Grace Hopper'])
  })
})
