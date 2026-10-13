# Verification status

Last updated 2026-10-13 (macOS, Docker CLI 29.8.1, Docker Compose v5.5.1).

## Summary

| Check | Command | Result |
| --- | --- | --- |
| Backend tests | `cd backend && ./.venv/bin/python -m pytest` | pass — 58 tests |
| Java tests | `cd java-validator && mvn test` | pass — 12 tests, BUILD SUCCESS |
| Frontend E2E | `cd frontend && npm run test:e2e` | pass — 8 Playwright tests |
| Frontend build | `cd frontend && npm run build` | pass — vue-tsc clean, bundle built |
| Compose config | `docker compose config` | pass (with dummy env) |
| Docker runtime | `docker compose up --build -d` | verified live on 2026-10-12 (see note below) |

## Update 2026-10-12 — Docker runtime verified + security fixes

The 2026-10-11 table above is the pre-Docker baseline. On a running daemon:

- Backend tests: **58 passed** (was 38; +20 across rate-limit/auth regressions,
  the guard red-team suite, and the LLM client-bound guard).
- `docker compose up -d --build`: backend, frontend, and java-validator images
  build; backend waits for a healthy java-validator; all three containers healthy.
- Frontend serves the SPA at `http://127.0.0.1:3000`; `backend`/`java-validator`
  `/health` return 200.
- **Security fixes verified live** (see `docs/security-model.md`):
  - Rotating `X-Forwarded-For` through nginx → `20×400` then `429`. Previously
    `25×400` with no `429`: the rate limit was bypassable.
  - Non-ASCII `X-API-Key` → `401`. Previously `500` (`hmac.compare_digest`
    raised `TypeError` on non-ASCII).
- **Availability fix verified live** (see `docs/security-model.md`): uploading a
  document through nginx (`:3000`) returned `504 Gateway Time-out` at 60s. The
  Gemini SDK was retrying a provider `503` with backoff for minutes while
  nginx's default 60s read timeout fired. With the LLM client bounded (60s,
  one attempt) and nginx at 90s, the same upload returns `200` within the bound
  — the graceful fallback path when the provider was unavailable, the summary
  when it was healthy.

## Why Docker runtime was not verified

The Docker daemon is not running in the environment where this work was done
(`docker info` fails). Image builds, container startup order, healthchecks,
nginx proxying, and CORS were validated only by static inspection.

## Still unverified (requires Docker)

Run these on a machine with a running daemon:

```bash
export TOKEN_VAULT_KEY="$(openssl rand -base64 32)"
export SECUREDOC_API_KEY="$(openssl rand -hex 32)"
docker compose up --build -d
curl -fsS http://127.0.0.1:8000/health           # backend health
curl -fsS http://127.0.0.1:8080/health           # Java validator health
curl -fsS http://127.0.0.1:3000/ >/dev/null      # frontend served
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

## One-command re-verification

```bash
./scripts/verify-all.sh
```

It runs every non-Docker check and, when the daemon is available, builds and
smoke-tests the full stack. Docker-dependent checks are reported as skipped
rather than passed when the daemon is absent.
