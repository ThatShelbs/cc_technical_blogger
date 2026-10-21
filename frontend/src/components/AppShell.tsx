import { FileText, Menu, Moon, Settings, Sun, SunMoon, Users, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link, NavLink } from 'react-router'

import { useActivePersona, useHealth } from '../api/hooks'
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

function ActivePersonaCard() {
  const { data: persona } = useActivePersona()
  if (!persona) return null
  return (
    <Link to={`/personas/${persona.id}`} className="block rounded-xl border border-line bg-surface-2 p-3 hover:border-accent">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">Writing as</p>
      <p className="truncate font-semibold">{persona.name}</p>
      <p className="text-xs text-muted">{persona.voice_soul_version ? `Voice soul v${persona.voice_soul_version}` : 'No voice soul yet'}</p>
    </Link>
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
            <ActivePersonaCard />
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
                <ActivePersonaCard />
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
