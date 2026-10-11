import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
  webServer: [
    {
      // Document-validation microservice (needs a JDK 21 on JAVA_HOME).
      command: 'mvn -q spring-boot:run',
      cwd: '../java-validator',
      url: 'http://127.0.0.1:8080/health',
      timeout: 180_000,
      reuseExistingServer: true,
    },
    {
      // FastAPI backend; GEMINI_API_KEY is left unset so the suite exercises the
      // graceful "llm unavailable" path instead of a real model call.
      command: './.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000',
      cwd: '../backend',
      env: {
        TOKEN_VAULT_KEY: 'test-e2e-vault-key',
        SECUREDOC_API_KEY: 'test-e2e-api-key',
        APP_ENV: 'test',
        AUDIT_LOG_PATH: '/tmp/securedoc-e2e-audit.log',
        DATABASE_URL: 'sqlite:////tmp/securedoc-e2e.db',
        JAVA_VALIDATOR_URL: 'http://127.0.0.1:8080',
      },
      url: 'http://127.0.0.1:8000/health',
      timeout: 120_000,
      reuseExistingServer: true,
    },
    {
      // Vite dev server; the proxy injects X-API-Key from this env var.
      command: 'npm run dev',
      cwd: '.',
      env: { SECUREDOC_API_KEY: 'test-e2e-api-key' },
      url: 'http://127.0.0.1:5173',
      timeout: 120_000,
      reuseExistingServer: true,
    },
  ],
})