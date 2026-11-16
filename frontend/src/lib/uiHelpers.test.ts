import { describe, expect, it } from 'vitest'

import { nextTabIndex } from './tabs'
import { toastReducer, type ToastItem } from '../components/useToast'
import { trapTarget } from './focusTrap'
import { matchHotkey, type KeyLike } from './hotkeys'
import { filterEntries, matchesQuery, type PaletteEntry } from './palette'

const key = (k: string, extra: Partial<KeyLike> = {}): KeyLike => ({ key: k, ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, ...extra })

describe('matchHotkey', () => {
  it('treats Ctrl and Cmd alike for mod', () => {
    expect(matchHotkey(key('k', { ctrlKey: true }), 'mod+k')).toBe(true)
    expect(matchHotkey(key('K', { metaKey: true }), 'mod+k')).toBe(true)
  })
  it('does not fire without the modifier or with extra ones', () => {
    expect(matchHotkey(key('k'), 'mod+k')).toBe(false)
    expect(matchHotkey(key('k', { ctrlKey: true, shiftKey: true }), 'mod+k')).toBe(false)
    expect(matchHotkey(key('k', { ctrlKey: true }), 'k')).toBe(false)
  })
  it('matches named keys and the bare question mark', () => {
    expect(matchHotkey(key('Enter', { ctrlKey: true }), 'mod+enter')).toBe(true)
    expect(matchHotkey(key('?', { shiftKey: true }), '?')).toBe(true)
  })
})

describe('nextTabIndex', () => {
  it('wraps with the arrow keys and jumps with Home/End', () => {
    expect(nextTabIndex('ArrowRight', 2, 3)).toBe(0)
    expect(nextTabIndex('ArrowLeft', 0, 3)).toBe(2)
    expect(nextTabIndex('Home', 2, 3)).toBe(0)
    expect(nextTabIndex('End', 0, 3)).toBe(2)
  })
  it('ignores other keys', () => {
    expect(nextTabIndex('a', 0, 3)).toBeNull()
    expect(nextTabIndex('ArrowRight', 0, 0)).toBeNull()
  })
})

describe('trapTarget', () => {
  const items = ['a', 'b', 'c']
  it('loops focus at both ends and leaves the middle alone', () => {
    expect(trapTarget(items, 'c', false)).toBe('a')
    expect(trapTarget(items, 'a', true)).toBe('c')
    expect(trapTarget(items, 'b', false)).toBeNull()
  })
  it('pulls focus back in from outside', () => {
    expect(trapTarget(items, 'x', false)).toBe('a')
    expect(trapTarget(items, null, true)).toBe('c')
  })
})

describe('toastReducer', () => {
  const toast = (id: number): ToastItem => ({ id, tone: 'info', message: `m${id}` })
  it('adds, dismisses and keeps only the newest four', () => {
    let state: ToastItem[] = []
    for (let i = 1; i <= 5; i++) state = toastReducer(state, { type: 'add', toast: toast(i) })
    expect(state.map((t) => t.id)).toEqual([2, 3, 4, 5])
    expect(toastReducer(state, { type: 'dismiss', id: 3 }).map((t) => t.id)).toEqual([2, 4, 5])
  })
})

describe('command palette filtering', () => {
  const entries: PaletteEntry[] = [
    { id: '1', label: 'New post', group: 'Actions', keywords: 'write' },
    { id: '2', label: 'Posts', group: 'Go to' },
    { id: '3', label: 'My first post about causal inference', group: 'Posts' },
  ]
  it('needs every word to match, in any order', () => {
    expect(matchesQuery(entries[2], 'causal post')).toBe(true)
    expect(matchesQuery(entries[0], 'new write')).toBe(true)
    expect(matchesQuery(entries[1], 'idea')).toBe(false)
  })
  it('ranks label prefixes first and caps the list', () => {
    expect(filterEntries(entries, 'post').map((e) => e.id)).toEqual(['2', '1', '3'])
    expect(filterEntries(entries, '', 2)).toHaveLength(2)
  })
})
