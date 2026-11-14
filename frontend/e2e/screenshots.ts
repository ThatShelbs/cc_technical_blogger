import type { Page } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const SCREENSHOTS = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../docs/screenshots')
// UPDATE_SCREENSHOTS=1 refreshes the README and docs screenshots in docs/screenshots.
const capture = process.env.UPDATE_SCREENSHOTS === '1'

/** Save a docs screenshot (only when UPDATE_SCREENSHOTS=1). */
export async function shot(page: Page, name: string, options: { fullPage?: boolean } = {}) {
  if (!capture) return
  mkdirSync(SCREENSHOTS, { recursive: true })
  await page.screenshot({ path: path.join(SCREENSHOTS, `${name}.png`), ...options })
}
