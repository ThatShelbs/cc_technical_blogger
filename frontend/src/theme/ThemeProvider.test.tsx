import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import { ThemeToggle } from '../components/AppShell'
import { ThemeProvider } from './ThemeProvider'

function renderToggle() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <ThemeProvider>
          <ThemeToggle />
        </ThemeProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ThemeToggle', () => {
  it('cycles day → night → system and remembers the choice', async () => {
    localStorage.setItem('proseferno-theme', 'light')
    renderToggle()
    expect(document.documentElement.dataset.theme).toBe('light')

    await userEvent.click(screen.getByRole('button', { name: /Day mode/ }))
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('proseferno-theme')).toBe('dark')

    await userEvent.click(screen.getByRole('button', { name: /Night mode/ }))
    expect(localStorage.getItem('proseferno-theme')).toBe('system')
    // jsdom's matchMedia (see setup) reports a light system theme.
    expect(document.documentElement.dataset.theme).toBe('light')
  })
})
