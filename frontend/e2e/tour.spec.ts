import { expect, test } from '@playwright/test'

import { shot } from './screenshots'

// Tests share one server and run in order: the tour looks at the seeded example, then removes it
// and walks the whole setup again with no files of the person's own.
test.describe.configure({ mode: 'serial' })

test('demo opens on a finished example post', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText(/Demo mode/)).toBeVisible()
  // No setup guide: the example persona is already on.
  await expect(page.getByRole('heading', { name: 'Posts', exact: true })).toBeVisible()
  await expect(page.getByText('Example', { exact: true }).first()).toBeVisible()

  await page.getByRole('link', { name: 'With Great Models Comes Great Responsibility (and a Pager)' }).last().click()
  await expect(page.getByText('This is an example post')).toBeVisible()
  await expect(page.locator('figure img')).toHaveCount(4, { timeout: 30_000 })
  await expect(page.getByText(/Author: Sample Author; Made with/).first()).toBeVisible()
  await shot(page, 'getting-started/05-demo-example')

  await page.getByRole('link', { name: 'Personas' }).first().click()
  await expect(page.getByText('3 of my posts')).toBeVisible()
  await expect(page.getByText('Voice profile v1', { exact: true })).toBeVisible()
})

test('the example persona has insights: a voice digest and charts', async ({ page }) => {
  await page.goto('/personas')
  await page.getByRole('link', { name: 'Sample Author' }).first().click()
  await page.getByRole('tab', { name: 'Insights' }).click()
  // The tab is in the URL, so it survives a reload.
  await expect(page).toHaveURL(/tab=insights/)
  await page.reload()
  await expect(page.getByRole('tab', { name: 'Insights' })).toHaveAttribute('aria-selected', 'true')

  // Claude's digest of the voice profile, with the voice mix counted from labeled sentences.
  await expect(page.getByRole('heading', { name: 'Tone & voice' })).toBeVisible()
  await expect(page.getByText('Mostly chatty, backed up by data.')).toBeVisible()
  await expect(page.getByRole('img', { name: /^Voice mix: Chatty 40%/ })).toBeVisible()
  await expect(page.getByText('Everyone peeks')).toBeVisible()

  // Charts measured from the samples and the example post.
  await expect(page.getByRole('heading', { name: 'Style fingerprint' })).toBeVisible()
  await expect(page.getByRole('img', { name: 'Formula flow across 1 post' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Track record' })).toBeVisible()
  await shot(page, 'persona-insights', { fullPage: true })

  await page.getByRole('button', { name: 'Refresh insights' }).click()
  await expect(page.getByRole('button', { name: 'Refresh insights' })).toBeEnabled({ timeout: 30_000 })
  await expect(page.getByText('Could not build the insights')).toHaveCount(0)
})

test('idea lab: brainstorm ten ideas, order them three ways, add a search, and write one', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Idea Lab' }).first().click()
  await expect(page.getByRole('heading', { name: 'Idea Lab', exact: true })).toBeVisible()
  await expect(page.getByText('No ideas yet')).toBeVisible()

  // The first brainstorm researches first, then writes and ranks the ideas.
  await page.getByRole('button', { name: 'Brainstorm 10 ideas' }).click()
  await expect(page.getByRole('button', { name: 'Outline & write' })).toHaveCount(10, { timeout: 90_000 })

  await page.getByRole('button', { name: 'Themes', exact: true }).click()
  await expect(page.locator('section h2').first()).toBeVisible()
  await page.getByRole('button', { name: 'Source approach', exact: true }).click()
  await expect(page.getByRole('heading', { name: /Live and Emerging/ })).toBeVisible()
  await expect(page.getByRole('heading', { name: /Portfolio Builder/ })).toBeVisible()
  await expect(page.getByRole('heading', { name: /Portfolio Expander/ })).toBeVisible()
  await shot(page, 'idea-lab', { fullPage: true })

  // The research the ideas came from, and one more search added to it.
  await page.getByRole('tab', { name: 'Research' }).click()
  await expect(page).toHaveURL(/tab=research/)
  await expect(page.getByRole('heading', { name: 'Agent frameworks add built-in evaluation' })).toBeVisible()
  await page.getByLabel('Send another search').fill('feature stores')
  await page.getByRole('button', { name: 'Search and add' }).click()
  await expect(page.getByRole('heading', { name: 'New this week: feature stores' })).toBeVisible({ timeout: 60_000 })

  await page.getByRole('tab', { name: 'Sources' }).click()
  await expect(page.getByRole('heading', { name: 'People to watch' })).toBeVisible()
  await expect(page.getByRole('switch', { name: 'Read Towards Data Science' })).toHaveAttribute('aria-checked', 'true')

  // Pick an idea and send it straight to the writer.
  await page.getByRole('tab', { name: 'Ideas' }).click()
  await page.getByRole('button', { name: 'Outline & write' }).first().click()
  await expect(page.getByRole('heading', { name: 'Outline', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'A/B test it' })).toBeVisible()
  await page.getByRole('button', { name: 'Write this post' }).click()
  await expect(page).toHaveURL(/\/projects\/\d+/)
  await expect(page.getByRole('heading', { name: 'Title', exact: true })).toBeVisible({ timeout: 90_000 })

  await page.getByRole('link', { name: 'Idea Lab' }).first().click()
  // The idea left the "to consider" list and now links to its post.
  await expect(page.getByRole('button', { name: 'Outline & write' })).toHaveCount(9)
  await page.getByRole('button', { name: 'Written (1)' }).click()
  await expect(page.getByRole('link', { name: 'Open the post' })).toBeVisible()

  // Save another idea; it lands in the saved bank next to the one now being written.
  await page.getByRole('button', { name: 'To consider (9)' }).click()
  await page
    .getByRole('button', { name: /^Save / })
    .first()
    .click()
  await page.getByRole('tab', { name: 'Saved bank' }).click()
  await expect(page.getByRole('button', { name: 'To write (1)' })).toBeVisible()
  await page.getByRole('button', { name: 'Add your own idea' }).click()
  await page.getByLabel('Title').fill('What our first churn model got wrong')
  await page.getByRole('button', { name: 'Add to the bank' }).click()
  await expect(page.getByRole('button', { name: 'What our first churn model got wrong', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'In progress (1)' }).click()
  await expect(page.getByText('Generated', { exact: true })).toBeVisible()
  await shot(page, 'idea-bank', { fullPage: true })
})

test('with no files of your own: remove the example, start from a ready-made voice, write a post', async ({ page }) => {
  await page.goto('/personas')
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: 'Remove example' }).click()
  await expect(page.getByText('No personas yet')).toBeVisible()

  // An empty app lands on the setup guide.
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /Welcome to Inferno Ghostwriter/ })).toBeVisible()
  await page.getByRole('button', { name: /^3 Persona$/ }).click()
  await page.getByLabel('Persona name').fill('No Files Writer')
  await page.getByRole('button', { name: 'Create and continue' }).click()

  // No writing: start fresh from a ready-made voice. Setup never dead-ends.
  await expect(page.getByRole('heading', { name: 'Where does your voice come from?' })).toBeVisible()
  await page.getByRole('radio', { name: /starting fresh/ }).click()
  await page.getByRole('button', { name: /Pick a voice/ }).click()
  await page.getByRole('button', { name: /The Dry-Wit Staff Engineer/ }).click()
  await page.getByRole('radio', { name: /starting fresh/ }).scrollIntoViewIfNeeded()
  await shot(page, 'getting-started/07b-start-fresh', { fullPage: true })
  await page.getByRole('button', { name: 'Use this voice' }).click()

  await page.getByRole('button', { name: 'Generate my voice profile' }).click()
  await expect(page.getByText('Version 1')).toBeVisible({ timeout: 60_000 })
  await page.getByRole('button', { name: 'Write my first post' }).click()

  await page.getByRole('button', { name: 'Use an example prompt' }).click()
  await page.getByRole('button', { name: /Write my post/ }).click()
  await expect(page.getByRole('heading', { name: 'Title', exact: true })).toBeVisible({ timeout: 90_000 })
  await expect(page.locator('figure img')).toHaveCount(4)
})
