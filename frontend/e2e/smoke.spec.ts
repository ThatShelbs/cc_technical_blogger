import { expect, test, type Page } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const SAMPLE = path.resolve(here, '../../examples/sample-post.md')
const SCREENSHOTS = path.resolve(here, '../../docs/screenshots')
// UPDATE_SCREENSHOTS=1 refreshes the README screenshots in docs/screenshots.
const capture = process.env.UPDATE_SCREENSHOTS === '1'

async function shot(page: Page, name: string) {
  if (capture) await page.screenshot({ path: path.join(SCREENSHOTS, `${name}.png`) })
}

test.beforeAll(() => {
  if (capture) mkdirSync(SCREENSHOTS, { recursive: true })
})

test('first run: persona, writing sample, voice soul, post, editor, export, themes', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('proseferno-theme', 'light'))
  await page.goto('/')

  // First run lands on the setup guide.
  await expect(page.getByRole('heading', { name: /Welcome to Prose/ })).toBeVisible()
  await expect(page.getByText(/Claude is simulated/)).toBeVisible()

  // Persona
  await page.getByRole('button', { name: /^3 Persona$/ }).click()
  await page.getByLabel('Persona name').fill('E2E Writer')
  await page.getByRole('button', { name: 'Create and continue' }).click()

  // Writing sample
  await expect(page.getByRole('heading', { name: 'Add posts you wrote' })).toBeVisible()
  await page.getByLabel('Choose sample files').setInputFiles(SAMPLE)
  await expect(page.getByText('Added 1 sample.')).toBeVisible()
  await page.getByRole('button', { name: 'Continue' }).click()

  // Voice soul (streams, then shows the measured baseline)
  await page.getByRole('button', { name: 'Generate my voice soul' }).click()
  await expect(page.getByText('Version 1')).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('Words per sentence')).toBeVisible()
  await shot(page, 'voice-soul')

  // New post from a single sentence
  await page.getByRole('button', { name: 'Write my first post' }).click()
  await page.getByLabel(/What should this post be about/).fill('Why pie charts are lame and what to use instead')
  await page.getByRole('button', { name: /Write my post/ }).click()
  await expect(page.getByText('Writing your post')).toBeVisible()

  // Editor with inline, credited images
  await expect(page.getByRole('heading', { name: 'Title options' })).toBeVisible({ timeout: 90_000 })
  await expect(page.locator('figure img')).toHaveCount(4)
  await expect(page.getByText(/Author: E2E Writer; Made with Claude Opus 5\.5 \(SVG\)/).first()).toBeVisible()
  await shot(page, 'editor-day')

  // Pick another title
  await page.getByRole('button', { name: 'Stop Baking Pies' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Stop Baking Pies' }).first()).toBeVisible()

  // Export dialog offers platform bundles
  await page.getByRole('button', { name: 'Export' }).click()
  await page.getByRole('radio', { name: 'Gumroad' }).click()
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: /Download bundle/ }).click()])
  expect(download.suggestedFilename()).toBe('stop-baking-pies-gumroad.zip')
  await page.getByRole('radio', { name: 'LinkedIn' }).click()
  await page.getByRole('button', { name: 'Write with Claude' }).click()
  await expect(page.getByLabel('LinkedIn feed post')).toHaveValue(/I stopped making pie charts/)
  await page.getByRole('button', { name: 'Close' }).click()

  // AI-detection report
  await expect(page.getByRole('heading', { name: 'Reads as human' })).toBeVisible()
  await page.getByRole('button', { name: /Full report/ }).click()
  await expect(page.getByText('Scan signals (calibrated to your own posts)')).toBeVisible()
  await page.getByRole('button', { name: 'Close' }).click()

  // Persona switcher in the sidebar
  await page.getByRole('button', { name: /Writing as/ }).click()
  await expect(page.getByRole('dialog', { name: 'Switch persona' })).toBeVisible()
  await page.keyboard.press('Escape')

  // Night mode
  await page.getByRole('button', { name: /Theme: Day mode/ }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await shot(page, 'editor-night')

  // Posts list shows the thumbnail
  await page.getByRole('link', { name: 'Posts' }).click()
  await expect(page.getByRole('link', { name: 'Stop Baking Pies' })).toBeVisible()
})
