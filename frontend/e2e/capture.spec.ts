import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const ASSETS = path.resolve(process.cwd(), '..', 'docs', 'assets')

test('capture: dashboard', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('API online', { exact: true })).toBeVisible()
  mkdirSync(ASSETS, { recursive: true })
  await page.screenshot({ path: path.join(ASSETS, 'dashboard.png'), fullPage: true })
})

test('capture: processed result', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Safe sample' }).click()
  await page.getByRole('button', { name: 'Process securely' }).click()
  await expect(page.getByRole('heading', { name: 'Sanitized payload' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Model output' })).toBeVisible()
  mkdirSync(ASSETS, { recursive: true })
  await page.screenshot({ path: path.join(ASSETS, 'processed.png'), fullPage: true })
})

test('capture: injection blocked', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Injection sample' }).click()
  await page.getByRole('button', { name: 'Process securely' }).click()
  await expect(page.getByRole('heading', { name: 'Request blocked' })).toBeVisible()
  mkdirSync(ASSETS, { recursive: true })
  await page.screenshot({ path: path.join(ASSETS, 'blocked.png'), fullPage: true })
})

test('capture: safe flow frames (assembled into a GIF)', async ({ page }) => {
  const frames = path.join(ASSETS, 'frames')
  mkdirSync(frames, { recursive: true })
  let n = 0

  await page.goto('/')
  await expect(page.getByText('API online', { exact: true })).toBeVisible()
  await page.screenshot({ path: path.join(frames, `f${String(n++).padStart(2, '0')}.png`), fullPage: false })

  await page.getByRole('button', { name: 'Safe sample' }).click()
  await page.screenshot({ path: path.join(frames, `f${String(n++).padStart(2, '0')}.png`), fullPage: false })

  await page.getByRole('button', { name: 'Process securely' }).click()
  await page.waitForTimeout(600)
  await page.screenshot({ path: path.join(frames, `f${String(n++).padStart(2, '0')}.png`), fullPage: false })

  await expect(page.getByRole('heading', { name: 'Sanitized payload' })).toBeVisible()
  await page.screenshot({ path: path.join(frames, `f${String(n++).padStart(2, '0')}.png`), fullPage: false })

  await expect(page.getByRole('heading', { name: 'Model output' })).toBeVisible()
  await page.waitForTimeout(400)
  await page.screenshot({ path: path.join(frames, `f${String(n++).padStart(2, '0')}.png`), fullPage: false })
})