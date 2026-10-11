# Verification status

Recorded on 2026-10-11 (macOS, Docker CLI 29.8.1, Docker Compose v5.5.1).

## Summary

| Check | Command | Result |
| --- | --- | --- |
| Backend tests | `cd backend && ./.venv/bin/python -m pytest` | pass — 38 tests |
| Java tests | `cd java-validator && mvn test` | pass — 12 tests, BUILD SUCCESS |
| Frontend build | `cd frontend && npm run build` | pass — vue-tsc clean, bundle built |
| Compose config | `docker compose config` | pass (with dummy env) |
| Docker runtime | `docker compose up --build -d` | **NOT RUN — daemon unavailable** |

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
