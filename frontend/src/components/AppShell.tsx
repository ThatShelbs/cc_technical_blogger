import { Check, ChevronDown, ChevronsUpDown, FileText, Menu, Moon, Settings, Sun, SunMoon, Users, X } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, NavLink } from 'react-router'

import { useHealth, usePersonaMutations, usePersonas } from '../api/hooks'
import type { PersonaOut } from '../api/types.gen'
import { useTheme, type ThemeMode } from '../theme/useTheme'
import { cx } from '../lib/cx'

const NAV = [
  { to: '/', label: 'Posts', icon: FileText, end: true },
  { to: '/personas', label: 'Personas', icon: Users, end: false },
  { to: '/settings', label: 'Settings', icon: Settings, end: false },
]

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <Link to="/" className="flex items-center gap-2.5" aria-label="Proseferno home">
      <img src="/logo-mark.svg" alt="" className="size-9 shrink-0" />
      {!compact && (
        <span className="text-xl font-extrabold tracking-tight">
          Prose<span className="flame-text">ferno</span>
        </span>
      )}
    </Link>
  )
}

export function ThemeToggle() {
  const { mode, setMode } = useTheme()
  const next: Record<ThemeMode, ThemeMode> = { light: 'dark', dark: 'system', system: 'light' }
  const Icon = mode === 'light' ? Sun : mode === 'dark' ? Moon : SunMoon
  const label = { light: 'Day mode', dark: 'Night mode', system: 'Match system' }[mode]
  return (
    <button
      type="button"
      onClick={() => setMode(next[mode])}
      className="inline-flex h-9 items-center gap-2 rounded-lg px-3 text-sm font-medium text-muted hover:bg-surface-2 hover:text-fg"
      aria-label={`Theme: ${label}. Click to change.`}
      title={`Theme: ${label}`}
    >
      <Icon className="size-4" aria-hidden />
      <span>{label}</span>
    </button>
  )
}

function versionText(persona: PersonaOut): string {
  if (!persona.voice_profile_version) return 'No voice profile yet'
  const label = persona.voice_profile_label ? ` · ${persona.voice_profile_label}` : ''
  return `Voice profile v${persona.voice_profile_version}${label}${persona.pinned_voice_profile_version ? ' (pinned)' : ''}`
}

/** "Writing as" card that opens a switcher for every persona and each one's voice profile versions. */
function PersonaSwitcher({ onNavigate }: { onNavigate?: () => void }) {
  const { data: personas } = usePersonas()
  const { activate, pinVersion } = usePersonaMutations()
  const [open, setOpen] = useState(false)
  const [expanded, setExpanded] = useState<number | null>(null)
  const panel = useRef<HTMLDivElement>(null)
  const active = personas?.find((p) => p.is_active)

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === 'Escape' : !panel.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  if (!personas?.length) return null
  const close = () => {
    setOpen(false)
    onNavigate?.()
  }
  const busy = activate.isPending || pinVersion.isPending
  const choose = (persona: PersonaOut, version?: number | null) => {
    if (!persona.is_active) activate.mutate(persona.id)
    if (version !== undefined && version !== persona.pinned_voice_profile_version) pinVersion.mutate({ id: persona.id, version })
  }

  return (
    <div ref={panel} className="relative">
      {open && (
        <div
          role="dialog"
          aria-label="Switch persona"
          className="absolute bottom-full left-0 z-30 mb-2 max-h-[70vh] w-72 overflow-y-auto rounded-xl border border-line bg-surface p-2 shadow-xl"
        >
          <p className="px-2 pt-1 pb-2 text-xs font-semibold tracking-wide text-muted uppercase">Personas</p>
          <ul className="space-y-1">
            {personas.map((persona) => {
              const showVersions = expanded === persona.id || (expanded === null && persona.is_active)
              return (
                <li key={persona.id} className={cx('rounded-lg', persona.is_active && 'bg-accent-soft')}>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => choose(persona)}
                      className="flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2 py-2 text-left hover:bg-surface-2"
                      aria-pressed={persona.is_active}
                    >
                      <span className={cx('size-2.5 shrink-0 rounded-full', persona.is_active ? 'bg-success' : 'border border-line')} aria-hidden />
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-semibold">{persona.name}</span>
                        <span className="block truncate text-xs text-muted">{versionText(persona)}</span>
                      </span>
                    </button>
                    {persona.voice_profile_versions.length > 1 && (
                      <button
                        type="button"
                        className="rounded-md p-1.5 text-muted hover:bg-surface-2 hover:text-fg"
                        aria-label={`${showVersions ? 'Hide' : 'Show'} versions of ${persona.name}`}
                        aria-expanded={showVersions}
                        onClick={() => setExpanded(showVersions ? -1 : persona.id)}
                      >
                        <ChevronDown className={cx('size-4 transition', showVersions && 'rotate-180')} />
                      </button>
                    )}
                  </div>
                  {showVersions && persona.voice_profile_versions.length > 1 && (
                    <ul className="ml-6 space-y-0.5 border-l border-line pb-2 pl-2" aria-label={`Voice profile versions of ${persona.name}`}>
                      <li>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => choose(persona, null)}
                          className="flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-xs hover:bg-surface-2"
                        >
                          <Check
                            className={cx(
                              'size-3.5 shrink-0',
                              persona.is_active && persona.pinned_voice_profile_version === null ? 'text-success' : 'invisible',
                            )}
                          />
                          Always the latest (v{persona.latest_voice_profile_version})
                        </button>
                      </li>
                      {persona.voice_profile_versions.map((v) => (
                        <li key={v.id}>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => choose(persona, v.version)}
                            className="flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-xs hover:bg-surface-2"
                          >
                            <Check
                              className={cx(
                                'size-3.5 shrink-0',
                                persona.is_active && persona.pinned_voice_profile_version === v.version ? 'text-success' : 'invisible',
                              )}
                            />
                            <span className="truncate">
                              v{v.version}
                              {v.label ? ` · ${v.label}` : ''}
                              <span className="text-muted"> · {new Date(v.created_at).toLocaleDateString()}</span>
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              )
            })}
          </ul>
          <div className="mt-2 flex gap-1 border-t border-line pt-2">
            {active && (
              <Link
                to={`/personas/${active.id}`}
                onClick={close}
                className="flex-1 rounded-md px-2 py-1.5 text-center text-xs font-semibold hover:bg-surface-2"
              >
                Edit {active.name}
              </Link>
            )}
            <Link to="/personas" onClick={close} className="flex-1 rounded-md px-2 py-1.5 text-center text-xs font-semibold hover:bg-surface-2">
              Manage personas
            </Link>
          </div>
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="flex w-full items-center gap-2 rounded-xl border border-line bg-surface-2 p-3 text-left hover:border-accent"
      >
        <span className="min-w-0 flex-1">
          <span className="block text-xs font-semibold tracking-wide text-muted uppercase">Writing as</span>
          <span className="block truncate font-semibold">{active?.name ?? 'No persona on'}</span>
          <span className="block truncate text-xs text-muted">{active ? versionText(active) : 'Choose one'}</span>
        </span>
        <ChevronsUpDown className="size-4 shrink-0 text-muted" aria-hidden />
      </button>
    </div>
  )
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Main" className="space-y-1">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            cx(
              'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-semibold transition',
              isActive ? 'bg-accent-soft text-fg' : 'text-muted hover:bg-surface-2 hover:text-fg',
            )
          }
        >
          <Icon className="size-4.5" aria-hidden />
          {label}
        </NavLink>
      ))}
    </nav>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const health = useHealth()
  return (
    <div className="min-h-screen bg-bg">
      {health.data?.demo && (
        <div className="flame-button px-4 py-1.5 text-center text-sm font-semibold text-white">
          Demo mode: AI responses and images are canned examples. No API keys are used.
        </div>
      )}
      <div className="flex">
        <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col gap-6 border-r border-line bg-surface px-4 py-5 lg:flex">
          <Logo />
          <NavItems />
          <div className="mt-auto space-y-3">
            <PersonaSwitcher />
            <ThemeToggle />
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <header className="flex items-center justify-between border-b border-line bg-surface px-4 py-3 lg:hidden">
            <Logo />
            <button type="button" className="rounded-lg p-2 hover:bg-surface-2" onClick={() => setOpen(true)} aria-label="Open menu">
              <Menu className="size-5" />
            </button>
          </header>
          {open && (
            <div className="fixed inset-0 z-40 bg-black/40 lg:hidden" onClick={() => setOpen(false)}>
              <div className="h-full w-72 space-y-6 bg-surface p-4" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between">
                  <Logo />
                  <button type="button" onClick={() => setOpen(false)} className="rounded-lg p-2 hover:bg-surface-2" aria-label="Close menu">
                    <X className="size-5" />
                  </button>
                </div>
                <NavItems onNavigate={() => setOpen(false)} />
                <PersonaSwitcher onNavigate={() => setOpen(false)} />
                <ThemeToggle />
              </div>
            </div>
          )}
          <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-10 lg:py-10">{children}</main>
        </div>
      </div>
    </div>
  )
}
