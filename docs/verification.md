# Verification status

Last updated 2026-10-13 (macOS laptop driving a remote Docker daemon, Docker CLI 29.8.1, Docker Compose v5.5.1).

## Summary

| Check | Command | Result |
| --- | --- | --- |
| Backend tests | `cd backend && ./.venv/bin/python -m pytest` | pass — 58 tests |
| Java tests | `cd java-validator && mvn test` | pass — 12 tests, BUILD SUCCESS |
| Frontend E2E | `cd frontend && npm run test:e2e` | pass — 8 Playwright tests |
| Frontend build | `cd frontend && npm run build` | pass — vue-tsc clean, bundle built |
| Compose config | `docker compose config` | pass (with dummy env) |
| Docker runtime | `docker compose up --build -d` | pass — verified live 2026-10-13 on a remote daemon |
| Smoke test | `make smoke` | pass — 7/7 checks |
| Audit logging | `make audit` | pass — LLM entry records `outcome: success` |
| Live Gemini inference | `make smoke` + `/api/process-document` | pass — `gemini-3.8-flash`, HTTP 200 |

## Docker runtime verification (2026-10-12)

On a running daemon:

- `docker compose up -d --build`: backend, frontend, and java-validator images
  build; backend waits for a healthy java-validator; all three containers healthy.
- Frontend serves the SPA (verified through nginx) on the remote host at port
  `3002`; the `backend` and `java-validator` `/health` checks return 200
  (checked inside the Compose network via `docker compose exec`).
- **Security and availability fixes re-checked live** (details in
  [`security-model.md`](security-model.md)): spoofed `X-Forwarded-For` now ends in
  `429`, a non-ASCII `X-API-Key` returns `401`, and an upload through nginx
  returns `200` within the bounded LLM timeout instead of a `504`.

## Live Gemini verification (2026-10-13)

Verified end-to-end against the running stack on the remote Docker daemon,
using a real Gemini API key supplied through the environment (never printed,
stored, or committed).

- **Model ID:** `gemini-3.8-flash` — the single default across the backend,
  `docker-compose.yml`, `docker-compose.prod.yml`, `.env.example`,
  `.env.production.example`, and the README configuration table.
- The synthetic sample invoice (`data/samples/invoice_sample.txt`) was submitted
  to `POST /api/process-document` through the Compose network and returned
  HTTP `200`.
- `llm_output` contains a genuine model-generated summary of the invoice
  (billing reference, outstanding amount, due date, and the redacted payment
  details).
- The response and the sanitized preview contain PII placeholders
  (`[PII_PERSON_*]`, `[PII_IBAN_CODE_*]`, `[PII_CREDIT_CARD_*]`,
  `[PII_PHONE_NUMBER_*]`, `[PII_EMAIL_ADDRESS_*]`); no raw PII (email, phone,
  IBAN, card number, or personal name) appears anywhere in the response body.
- The audit entry for the call records `"outcome": "success"` and
  `"model": "gemini-3.8-flash"` with metadata only — no raw PII or document
  text.

## Re-verification checklist (requires a Docker daemon)

Run these wherever the Docker CLI points at the daemon (local or remote):

```bash
export TOKEN_VAULT_KEY="$(openssl rand -base64 32)"
export SECUREDOC_API_KEY="$(openssl rand -hex 32)"
docker compose up --build -d
docker compose exec backend python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"  # backend health
docker compose exec java-validator wget -q -O - http://127.0.0.1:8080/health >/dev/null   # Java validator health
docker compose exec frontend wget -q -O - http://127.0.0.1/ >/dev/null                    # frontend served
make smoke                                        # end-to-end API checks
make audit                                        # audit log written
docker compose down
```

- [ ] All three images build (backend, frontend/nginx, java-validator).
- [ ] `backend` waits for `java-validator` to become healthy before serving.
- [ ] spaCy `en_core_web_lg` loads inside the backend container.
- [ ] Named volume `securedoc_data` is writable by `appuser` (uid 10001).
- [ ] nginx serves the SPA and proxies `/api` + `/health` to `backend:8000`.
- [ ] Same-origin calls succeed without CORS errors.
- [ ] Missing/invalid `X-API-Key` returns `401`.
- [ ] Injection payload returns `400`; audit log records both outcomes.
- [ ] With `GEMINI_API_KEY` in the environment, a document returns a model
      summary and the audit entry shows `"outcome": "success"`.

## One-command re-verification

```bash
./scripts/verify-all.sh
```

It runs every non-Docker check and, when the daemon is available, builds and
smoke-tests the full stack. Docker-dependent checks are reported as skipped
rather than passed when the daemon is absent.
