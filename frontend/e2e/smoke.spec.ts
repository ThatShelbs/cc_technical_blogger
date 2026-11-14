import { expect, test } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { shot } from './screenshots'

const here = path.dirname(fileURLToPath(import.meta.url))
const SAMPLE = path.resolve(here, 'fixtures/sample-post.md')

test('first run: persona, writing sample, voice profile, post, editor, export, themes', async ({ page }) => {
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

  // Voice profile (streams, then shows the measured baseline)
  await page.getByRole('button', { name: 'Generate my voice profile' }).click()
  await expect(page.getByText('Version 1')).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('Words per sentence')).toBeVisible()
  await shot(page, 'voice-profile')

  // New post from a single sentence
  await page.getByRole('button', { name: 'Write my first post' }).click()
  await page.getByLabel(/What should this post be about/).fill('Why pie charts are lame and what to use instead')
  // Formula: the type is read from the brief, and a shuffle draws parts that suit it
  await page.getByLabel(/What should this post be about/).fill('How to replace a pie chart')
  await expect(page.getByRole('option', { name: 'Automatic: How-to' })).toBeAttached()
  await page.getByRole('button', { name: 'Shuffle the formula' }).click()
  await expect(page.getByLabel('Body', { exact: true })).not.toHaveValue('auto')
  await page.getByRole('button', { name: 'Shuffle the closer' }).click()
  await expect(page.getByLabel('Closer', { exact: true })).not.toHaveValue('auto')
  await page.getByLabel(/What should this post be about/).fill('Why pie charts are lame and what to use instead')
  // Then an article type chosen by hand, its classic parts, and a different opener
  await page.getByLabel('Article type').selectOption({ label: 'Opinion / thought leadership' })
  await page.getByRole('button', { name: /Use the classic opinion formula/ }).click()
  await expect(page.getByLabel('Opener', { exact: true })).toHaveValue('contrarian')
  await page.getByLabel('Opener', { exact: true }).selectOption({ label: 'Joke: the confession' })
  await shot(page, 'formula')
  await page.getByRole('button', { name: /Write my post/ }).click()
  await expect(page.getByText('Writing your post')).toBeVisible()

  // Editor with inline, credited images
  await expect(page.getByRole('heading', { name: 'Title', exact: true })).toBeVisible({ timeout: 90_000 })
  await expect(page.getByRole('button', { name: /New options/ })).toBeVisible()
  await expect(page.locator('figure img')).toHaveCount(4)
  await expect(page.getByText(/Author: E2E Writer; Made with Claude Opus 5\.5 \(SVG\)/).first()).toBeVisible()
  await shot(page, 'editor-day')

  // References: five sources, quotes and resources worked into the post, each one redrawable
  await expect(page.getByRole('heading', { name: 'References' })).toBeVisible()
  await expect(page.getByText('5 of 5 in the post')).toBeVisible()
  await expect(page.getByRole('button', { name: /Show actions/ })).toHaveCount(5)
  const source = page.getByRole('listitem', { name: /^Source: / })
  const before = (await source.getByRole('link').textContent()) ?? ''
  await source.getByRole('button', { name: 'Redraw' }).click()
  await expect(source.getByRole('link')).not.toHaveText(before, { timeout: 60_000 })
  await expect(page.getByText('5 of 5 in the post')).toBeVisible()

  // Pick another title
  await page.getByRole('button', { name: 'Stop Baking Pies', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Stop Baking Pies' }).first()).toBeVisible()

  // Tweak with feedback keeps the post and its images, then undo it
  await page.getByLabel(/Tweak with feedback/).fill('Add a joke to the opening')
  await page.getByRole('button', { name: 'Apply feedback' }).click()
  await expect(page.getByText('Feedback applied')).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText(/nobody stopped them/)).toBeVisible()
  await expect(page.locator('figure img')).toHaveCount(4)
  await page.getByRole('button', { name: 'Undo last change' }).click()
  await expect(page.getByText(/nobody stopped them/)).toHaveCount(0)

  // Highlight a sentence in the preview, compact it in place, then undo
  const sentence = 'Bar charts. Seriously, bar charts.'
  await page.evaluate((needle) => {
    const walker = document.createTreeWalker(document.querySelector('.article')!, NodeFilter.SHOW_TEXT)
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const at = node.textContent?.indexOf(needle) ?? -1
      if (at < 0) continue
      const range = document.createRange()
      range.setStart(node, at)
      range.setEnd(node, at + needle.length)
      const selection = window.getSelection()!
      selection.removeAllRanges()
      selection.addRange(range)
      return
    }
    throw new Error('sentence not found')
  }, sentence)
  await expect(page.getByRole('toolbar', { name: 'Section actions' })).toBeVisible()
  await page.getByRole('button', { name: 'Compact' }).click()
  await expect(page.getByText(/Bar charts win\./)).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText(sentence)).toHaveCount(0)
  await expect(page.locator('figure img')).toHaveCount(4)
  await page.getByRole('button', { name: 'Undo last change' }).click()
  await expect(page.getByText(sentence)).toBeVisible()

  // Brief & settings: the original brief, the planned outline, every dial
  await page.getByRole('button', { name: 'Edit brief & settings' }).click()
  const settings = page.getByRole('dialog', { name: 'Brief & settings' })
  await expect(settings.getByLabel(/Brief or outline/)).toHaveValue('Why pie charts are lame and what to use instead')
  await settings.getByRole('button', { name: /Outline Claude planned/ }).click()
  await settings.getByRole('button', { name: 'Use as my outline' }).click()
  await expect(settings.getByLabel(/Brief or outline/)).toHaveValue(/- Why People Love Pies/)
  await expect(settings.getByLabel('Publishing on')).toBeVisible()
  await expect(settings.getByLabel(/Audience/)).toBeVisible()
  await expect(settings.getByLabel('Opener', { exact: true })).toHaveValue('joke_confession')
  await shot(page, 'post-settings')
  await settings.getByRole('button', { name: 'Close', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Try another formula' })).toBeVisible()
  await expect(page.getByText('Opinion / thought leadership · Joke: the confession · Build the argument · One-line kicker')).toBeVisible()

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

  // Publish: the post is compared with what was generated; a hit's secret sauce goes into the playbook
  const teach = page
    .locator('div')
    .filter({ has: page.getByRole('heading', { name: 'Teach the persona' }) })
    .last()
  await expect(teach.getByText(/You changed \d+% of the generated text/)).toBeVisible()
  await teach.getByRole('button', { name: 'Compare' }).click()
  await expect(page.getByRole('dialog', { name: 'Generated vs. your version' }).locator('del').first()).toBeVisible()
  await page.getByRole('button', { name: 'Close' }).click()
  await page.getByRole('button', { name: 'Published', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Too early' })).toHaveAttribute('aria-pressed', 'true')
  await expect(teach.getByText('From your edits')).toBeVisible()
  await expect(teach.getByText(/Nothing to change|To review/)).toBeVisible({ timeout: 30_000 })
  await page.getByRole('button', { name: 'Good traction' }).click()
  const sauce = teach.getByRole('listitem').filter({ hasText: 'Secret sauce' })
  await sauce.getByRole('button', { name: 'Review 2 suggestions' }).click({ timeout: 30_000 })
  const review = page.getByRole('dialog', { name: /^Secret sauce: / })
  await expect(review.getByText('Pick a side in the title and defend it in the first paragraph.')).toBeVisible()
  await review.getByRole('button', { name: 'Apply 2' }).click()
  await expect(sauce.getByText('Applied')).toBeVisible({ timeout: 30_000 })
  await sauce.getByRole('link', { name: /persona.s evolution/ }).click()
  await expect(page.getByRole('tab', { name: /Evolution/ })).toHaveAttribute('aria-selected', 'true')
  const playbook = page.getByRole('listitem').filter({ has: page.getByRole('button', { name: 'Forget this playbook entry' }) })
  await expect(playbook.filter({ hasText: 'Pick a side in the title and defend it in the first paragraph.' })).toBeVisible()
  await expect(playbook).toHaveCount(2)
  await page.goBack()
  await expect(page.getByRole('button', { name: 'Good traction' })).toHaveAttribute('aria-pressed', 'true')

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
  await expect(page.getByText('Good traction')).toBeVisible()
  await page.getByRole('button', { name: /^Draft/ }).click()
  await expect(page.getByRole('link', { name: 'Stop Baking Pies' })).toHaveCount(0)
  await page.getByRole('button', { name: /^Published/ }).click()
  await expect(page.getByRole('link', { name: 'Stop Baking Pies' })).toBeVisible()
})
