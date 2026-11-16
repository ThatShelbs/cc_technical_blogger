import { Search } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router'

import { usePersonaMutations, usePersonas, useProjects } from '../api/hooks'
import { useTheme } from '../theme/useTheme'
import { cx } from '../lib/cx'
import { filterEntries, type PaletteEntry } from '../lib/palette'

interface Command extends PaletteEntry {
  run: () => void
}

/** Ctrl/Cmd+K: jump to any page, post or persona, or run a common action, from the keyboard. */
export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const { data: projects } = useProjects()
  const { data: personas } = usePersonas()
  const { activate } = usePersonaMutations()
  const { setMode } = useTheme()
  const [query, setQuery] = useState('')
  const [cursor, setCursor] = useState(0)
  const dialog = useRef<HTMLDialogElement>(null)
  const input = useRef<HTMLInputElement>(null)

  const commands = useMemo<Command[]>(() => {
    const go = (to: string) => () => navigate(to)
    const list: Command[] = [
      { id: 'new', group: 'Actions', label: 'New post', keywords: 'write create project', run: go('/projects/new') },
      { id: 'posts', group: 'Go to', label: 'Posts', run: go('/') },
      { id: 'ideas', group: 'Go to', label: 'Idea Lab', keywords: 'ideas research brainstorm', run: go('/ideas') },
      { id: 'personas', group: 'Go to', label: 'Personas', keywords: 'voice profile', run: go('/personas') },
      { id: 'settings', group: 'Go to', label: 'Settings', keywords: 'api key connection', run: go('/settings') },
      { id: 'theme-light', group: 'Actions', label: 'Switch to day mode', keywords: 'theme light', run: () => setMode('light') },
      { id: 'theme-dark', group: 'Actions', label: 'Switch to night mode', keywords: 'theme dark', run: () => setMode('dark') },
      { id: 'theme-system', group: 'Actions', label: 'Match system theme', keywords: 'theme auto', run: () => setMode('system') },
    ]
    for (const persona of personas ?? []) {
      list.push({ id: `persona-${persona.id}`, group: 'Personas', label: persona.name, keywords: 'open edit', run: go(`/personas/${persona.id}`) })
      if (!persona.is_active) {
        list.push({
          id: `activate-${persona.id}`,
          group: 'Actions',
          label: `Write as ${persona.name}`,
          keywords: 'turn on switch persona',
          run: () => activate.mutate(persona.id),
        })
      }
    }
    for (const project of projects ?? []) {
      list.push({ id: `post-${project.id}`, group: 'Posts', label: project.title || 'Untitled post', run: go(`/projects/${project.id}`) })
    }
    return list
  }, [navigate, projects, personas, activate, setMode])

  const results = useMemo(() => filterEntries(commands, query) as Command[], [commands, query])

  useEffect(() => {
    const el = dialog.current
    if (!el) return
    if (open && !el.open) {
      el.showModal?.()
      input.current?.focus()
    }
    if (!open && el.open) el.close?.()
  }, [open])

  const close = () => {
    setQuery('')
    setCursor(0)
    onClose()
  }
  const choose = (command: Command | undefined) => {
    if (!command) return
    close()
    command.run()
  }
  const active = Math.min(cursor, Math.max(0, results.length - 1))

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setCursor((active + 1) % Math.max(1, results.length))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setCursor((active - 1 + results.length) % Math.max(1, results.length))
    } else if (event.key === 'Enter') {
      event.preventDefault()
      choose(results[active])
    }
  }

  return (
    <dialog
      ref={dialog}
      onClose={close}
      onCancel={close}
      aria-label="Command palette"
      className="m-auto mt-[12vh] w-[calc(100%-2rem)] max-w-xl rounded-2xl border border-line bg-surface p-0 text-fg shadow-2xl backdrop:bg-black/50"
    >
      {open && (
        <div onKeyDown={onKeyDown}>
          <div className="flex items-center gap-3 border-b border-line px-4">
            <Search className="size-4 shrink-0 text-muted" aria-hidden />
            <input
              ref={input}
              autoFocus
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setCursor(0)
              }}
              role="combobox"
              aria-expanded
              aria-controls="palette-results"
              aria-activedescendant={results[active] ? `palette-${results[active].id}` : undefined}
              aria-label="Search posts, personas and actions"
              placeholder="Search posts, personas and actions…"
              className="h-12 w-full bg-transparent text-base outline-none placeholder:text-muted/70"
            />
            <kbd className="rounded border border-line px-1.5 py-0.5 text-xs text-muted">Esc</kbd>
          </div>
          <ul id="palette-results" role="listbox" aria-label="Results" className="max-h-[50vh] overflow-y-auto p-2">
            {results.length === 0 && <li className="px-3 py-6 text-center text-sm text-muted">Nothing matches “{query}”.</li>}
            {results.map((command, index) => (
              <li key={command.id} role="presentation">
                <button
                  type="button"
                  id={`palette-${command.id}`}
                  role="option"
                  aria-selected={index === active}
                  tabIndex={-1}
                  onMouseMove={() => setCursor(index)}
                  onClick={() => choose(command)}
                  className={cx('flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm', index === active && 'bg-accent-soft')}
                >
                  <span className="truncate font-medium">{command.label}</span>
                  <span className="shrink-0 text-xs text-muted">{command.group}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </dialog>
  )
}
