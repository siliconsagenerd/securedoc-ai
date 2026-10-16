import { expect, test } from '@playwright/test'

test('standard invoice example shows illustrative result only', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Standard invoice' }).click()
  await page.getByRole('button', { name: 'Process securely' }).click()

  await expect(page.getByRole('heading', { name: 'Sanitized payload' })).toBeVisible()
  await expect(page.getByText('Illustrative sample — not live model output')).toBeVisible()
  await expect(page.getByText('Illustratives Beispiel — keine Live-Modellantwort')).toBeVisible()
  await expect(page.locator('.results .panel').filter({ hasText: 'Model output' }).locator('pre')).toContainText('Illustrative result')
})

test('invoice with synthetic personal data shows illustrative result only', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Invoice with synthetic personal data' }).click()
  await page.getByRole('button', { name: 'Process securely' }).click()

  await expect(page.getByRole('heading', { name: 'Sanitized payload' })).toBeVisible()
  await expect(page.getByText('Illustrative sample — not live model output')).toBeVisible()
  await expect(page.locator('.badges .badge').first()).toBeVisible()
})

test('malicious example stays blocked and shows illustrative label', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Document with an embedded malicious instruction' }).click()
  await page.getByRole('button', { name: 'Process securely' }).click()

  await expect(page.getByRole('heading', { name: 'Request blocked' })).toBeVisible()
  await expect(page.getByText('Illustrative sample — not live model output')).toBeVisible()
  await expect(page.getByText('Illustratives Beispiel — keine Live-Modellantwort')).toBeVisible()
})

test('arbitrary input keeps the honest unavailable state', async ({ page }) => {
  await page.goto('/')
  await page.getByPlaceholder('Paste a document containing sensitive data…').fill(
    'Arbitrary document text for a processing check.',
  )
  await page.getByRole('button', { name: 'Process securely' }).click()

  await expect(page.getByRole('heading', { name: 'Sanitized payload' })).toBeVisible()
  await expect(page.getByText('Illustrative sample — not live model output')).toHaveCount(0)
  await expect(page.locator('.results .panel').filter({ hasText: 'Model output' }).locator('pre')).toContainText(
    'LLM provider is not configured',
  )
  await expect(page.getByText('unavailable state')).toBeVisible()
})

test('edited example text does not get illustrative label', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Standard invoice' }).click()
  await page.getByPlaceholder('Paste a document containing sensitive data…').fill('changed text')
  await page.getByRole('button', { name: 'Process securely' }).click()

  await expect(page.getByRole('heading', { name: 'Sanitized payload' })).toBeVisible()
  await expect(page.getByText('Illustrative sample — not live model output')).toHaveCount(0)
})
