import { expect, test } from '@playwright/test'

const SAFE_DOC = `Dear team, please review the invoice from Alice Johnson.
Contact: alice.johnson@example.com, phone +49 151 12345678.
Bank transfer to IBAN DE89 3704 0044 0532 0130 00 by Friday.`

test('dashboard loads with the API online', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'SecureDoc AI' })).toBeVisible()
  await expect(page.getByText('API online', { exact: true })).toBeVisible()
})

test('safe document is processed, redacted, and audited', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Safe sample' }).click()
  await page.getByRole('button', { name: 'Process securely' }).click()

  // PII entities were detected and shown as badges.
  await expect(page.getByRole('heading', { name: 'Sanitized payload' })).toBeVisible()
  await expect(page.locator('.badges .badge').first()).toBeVisible()

  // Sanitized output contains placeholders, not the raw values.
  const preview = page.locator('pre').first()
  await expect(preview).toContainText('[PII_EMAIL_ADDRESS')
  await expect(preview).not.toContainText('alice.johnson@example.com')
  await expect(preview).not.toContainText('DE89 3704 0044 0532 0130 00')

  // Model output: graceful "LLM unavailable" state (no GEMINI_API_KEY in tests).
  await expect(page.getByRole('heading', { name: 'Model output' })).toBeVisible()
  await expect(page.locator('.results .panel').filter({ hasText: 'Model output' }).locator('pre')).toContainText(
    'LLM provider is not configured',
  )

  // Audit event id is displayed.
  await expect(page.getByText(/audit event [0-9a-f-]{36}/)).toBeVisible()
})

test('injection payload is blocked with risk score and categories', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Injection sample' }).click()
  await page.getByRole('button', { name: 'Process securely' }).click()

  await expect(page.getByRole('heading', { name: 'Request blocked' })).toBeVisible()
  await expect(page.getByText(/score \d+\/100/)).toBeVisible()
  await expect(page.locator('.alert-panel .badge.warn').getByText('instruction_override')).toBeVisible()
  await expect(page.getByText(/Nothing was sent to the model/)).toBeVisible()
})

test('upload flow works with a synthetic txt file', async ({ page }) => {
  await page.goto('/')
  await page.setInputFiles('input[type="file"]', {
    name: 'e2e-invoice.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('Contact jane.doe@example.com about invoice DE89 3704 0044 0532 0130 00.'),
  })

  await expect(page.locator('.filechip')).toContainText('e2e-invoice.txt')
  await page.getByRole('button', { name: 'Upload & process' }).click()

  await expect(page.getByRole('heading', { name: 'Sanitized payload' })).toBeVisible()
  await expect(page.locator('.results .meta')).toContainText('e2e-invoice.txt')
  await expect(page.locator('.results .panel').filter({ hasText: 'Sanitized payload' }).locator('pre')).toContainText(
    '[PII_EMAIL_ADDRESS',
  )
})