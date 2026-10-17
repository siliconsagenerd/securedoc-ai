import { expect, test } from '@playwright/test'

test('standard invoice example shows illustrative result only', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Standard invoice' }).click()
  await page.getByRole('button', { name: 'Process securely' }).click()

  await expect(page.getByRole('heading', { name: 'Sanitized payload' })).toBeVisible()
  await expect(page.getByText('Illustrative sample — not live model output')).toBeVisible()
  await expect(page.getByText('Illustratives Beispiel — keine Live-Modellantwort')).toBeVisible()
  await expect(page.locator('.results .panel').filter({ hasText: 'Model output' }).locator('pre')).toContainText('Illustrative invoice summary')
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

test('generic request failure keeps pipeline unconfirmed', async ({ page }) => {
  await page.goto('/')
  await page.route('**/api/process-document', route =>
    route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ message: 'Internal Server Error' }) })
  )
  await page.getByPlaceholder('Paste a document containing sensitive data…').fill('Arbitrary synthetic text for failure review.')
  await page.getByRole('button', { name: 'Process securely' }).click()

  await expect(page.locator('.inline-alert')).toContainText('Request failed — HTTP 500')
  await expect(page.locator('.inline-alert')).toContainText('Pipeline outcome unavailable')
  await expect(page.locator('.trace-detail', { hasText: 'not confirmed' })).toHaveCount(5)
  await expect(page.getByText('Illustrative sample — not live model output')).toHaveCount(0)
  await expect(page.getByText('Model — SAMPLE')).toHaveCount(0)
  await expect(page.locator('.results')).toHaveCount(0)
})
