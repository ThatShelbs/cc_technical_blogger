import { describe, expect, it } from 'vitest'

import type { FormulaCatalogOut, FormulaOption, FormulaOut } from '../api/types.gen'
import { applySaved, buildFormula, classicFormula, effective, formulaFrom, groupOptions, isAutomatic, matchesSaved, pickChoice, pickNote } from './formula'

const option = (id: string, group: string): FormulaOption => ({ id, label: id.toUpperCase(), summary: '', group, guide: '' })
const CATALOG: FormulaCatalogOut = {
  article_types: [{ id: 'tutorial', label: 'Tutorial', summary: '', guide: '', openers: ['result'], bodies: ['build', 'steps'], closers: ['dare'] }],
  openers: [option('confession', 'Joke'), option('swerve', 'Joke'), option('result', 'Story')],
  bodies: [option('steps', 'Teach'), option('build', 'Teach'), option('arc', 'Story')],
  closers: [option('dare', 'Hand it over'), option('kicker', 'Land it')],
}
const SAVED: FormulaOut = {
  id: 3,
  name: 'War story',
  description: '',
  article_type: 'auto',
  opener: 'confession',
  body: 'auto',
  closer: 'kicker',
  opener_note: '',
  body_note: 'Keep the dead ends.',
  closer_note: '',
  label: '',
  created_at: '',
}

describe('formula state', () => {
  it('stores nothing when a pick equals what the persona already gives', () => {
    const defaults = { opener: 'confession', closer_note: 'No recap.' }
    expect(pickChoice(defaults, 'opener', 'confession')).toEqual({ opener: null })
    expect(pickChoice(defaults, 'opener', 'auto')).toEqual({ opener: 'auto' })
    expect(pickChoice(undefined, 'body', 'auto')).toEqual({ body: null })
    expect(pickNote(defaults, 'closer_note', '')).toEqual({ closer_note: '' })
    expect(pickNote(defaults, 'closer_note', 'No recap.')).toEqual({ closer_note: null })
  })

  it('builds a payload of only what was set and reads it back', () => {
    const state = { article_type: 'tutorial', opener: null, body: 'auto', opener_note: '', closer_note: null }
    expect(buildFormula(state)).toEqual({ article_type: 'tutorial', body: 'auto', opener_note: '' })
    expect(formulaFrom({ humor: 3, article_type: 'tutorial', opener: null, body_note: 'x' })).toEqual({ article_type: 'tutorial', body_note: 'x' })
  })

  it('shows the post choice over the persona default, and recognises a saved formula', () => {
    const formula = effective({ closer: 'kicker' }, { opener: 'confession', body_note: 'Keep the dead ends. ' })
    expect(formula).toMatchObject({ article_type: 'auto', opener: 'confession', closer: 'kicker', body_note: 'Keep the dead ends.' })
    expect(matchesSaved(formula, SAVED)).toBe(true)
    expect(matchesSaved(effective(applySaved(SAVED), { opener: 'swerve' }), SAVED)).toBe(true)
    expect(isAutomatic(formula)).toBe(false)
    expect(isAutomatic(effective({}))).toBe(true)
  })

  it('lists the styles that fit the article type first, then the rest by family', () => {
    const type = CATALOG.article_types[0]
    expect(classicFormula(type)).toEqual({ opener: 'result', body: 'build', closer: 'dare' })
    expect(groupOptions(CATALOG.bodies, type.bodies, type.label).map((g) => [g.label, g.options.map((o) => o.id)])).toEqual([
      ['Good fit for Tutorial', ['build', 'steps']],
      ['Story', ['arc']],
    ])
    expect(groupOptions(CATALOG.openers, undefined).map((g) => g.label)).toEqual(['Joke', 'Story'])
  })
})
