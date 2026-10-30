import { expect, test } from '@playwright/test'

// Tests share one server and run in order: the tour looks at the seeded example, then removes it
// and walks the whole setup again with no files of the person's own.
test.describe.configure({ mode: 'serial' })

test('demo opens on a finished example post', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText(/Demo mode/)).toBeVisible()
  // No setup guide: the example persona is already on.
  await expect(page.getByRole('heading', { name: 'Posts', exact: true })).toBeVisible()
  await expect(page.getByText('Example', { exact: true }).first()).toBeVisible()

  await page.getByRole('link', { name: 'Pie Charts Are Lame' }).last().click()
  await expect(page.getByText('This is an example post')).toBeVisible()
  await expect(page.locator('figure img')).toHaveCount(4, { timeout: 30_000 })
  await expect(page.getByText(/Author: Sample Author; Made with/).first()).toBeVisible()

  await page.getByRole('link', { name: 'Personas' }).first().click()
  await expect(page.getByText('3 of my posts')).toBeVisible()
  await expect(page.getByText('Voice profile v1', { exact: true })).toBeVisible()
})

test('with no files of your own: remove the example, use the sample posts, write a post', async ({ page }) => {
  await page.goto('/personas')
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: 'Remove example' }).click()
  await expect(page.getByText('No personas yet')).toBeVisible()

  // An empty app lands on the setup guide.
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /Welcome to Prose/ })).toBeVisible()
  await page.getByRole('button', { name: /^3 Persona$/ }).click()
  await page.getByLabel('Persona name').fill('No Files Writer')
  await page.getByRole('button', { name: 'Create and continue' }).click()

  // No upload: the bundled sample posts unblock setup.
  await expect(page.getByText('No posts handy?')).toBeVisible()
  await page.getByRole('button', { name: 'Use 3 sample posts' }).click()
  await expect(page.getByText('Added 3 sample posts.')).toBeVisible()
  await page.getByRole('button', { name: 'Continue' }).click()

  await page.getByRole('button', { name: 'Generate my voice profile' }).click()
  await expect(page.getByText('Version 1')).toBeVisible({ timeout: 60_000 })
  await page.getByRole('button', { name: 'Write my first post' }).click()

  await page.getByRole('button', { name: 'Use an example prompt' }).click()
  await page.getByRole('button', { name: /Write my post/ }).click()
  await expect(page.getByRole('heading', { name: 'Title', exact: true })).toBeVisible({ timeout: 90_000 })
  await expect(page.locator('figure img')).toHaveCount(4)
})
