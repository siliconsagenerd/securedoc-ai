# SecureDoc AI

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Java 21](https://img.shields.io/badge/java-21-ED8B00?logo=openjdk&logoColor=white)](https://openjdk.org/)
[![Vue 3](https://img.shields.io/badge/vue-3-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/docker-compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![tests](https://img.shields.io/badge/tests-58%20pytest%20%C2%B7%2012%20mvn%20%C2%B7%208%20e2e-2ea44f)](https://github.com/siliconsagenerd/securedoc-ai)

**A security layer for LLM document processing.** Sensitive data is redacted and
encrypted **locally** before any text reaches an external model, prompt-injection
attempts are scored and blocked, uploads are validated by a separate Java service,
and every decision is written to an append-only audit log — aligned with GDPR
data-minimisation principles.

```mermaid
flowchart LR
    U[Vue 3 dashboard] -->|same-origin /api| F[nginx proxy<br/>injects X-API-Key]
    F --> B[FastAPI backend]
    B --> J[Java validator<br/>Spring Boot]
    B --> G{Injection guard<br/>risk 0-100}
    G -->|blocked| A[(Audit log)]
    G -->|allowed| P[Presidio redaction<br/>+ Fernet vault]
    P -->|sanitized text only| M[Gemini API]
    M --> B
    B --> A
    B --> U
```

Raw values never reach the model — here is the flow in practice:

![SecureDoc AI — live demo](docs/assets/demo-flow.gif)

| Safe document, processed & redacted                                     | Prompt injection, blocked                                            |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------- |
| ![Processed result](docs/assets/processed.png)                          | ![Blocked request](docs/assets/blocked.png)                         |

![Dashboard](docs/assets/dashboard.png)

## Why this project fits an AI & Security role (applied for ELO)

This repository is a deliberately small, end-to-end system built to demonstrate
the skills an *KI & Security* engineer needs in practice:

| ELO / AI-security domain                          | What this project shows                                          |
| ------------------------------------------------- | ---------------------------------------------------------------- |
| **Securing the AI supply chain**                  | LLM access handled like any other external dependency: an API key injected by the edge proxy, never shipped in client code, validated before use |
| **Prompt-injection & evasion defence** (`OWASP LLM-01`) | Rule-based 0–100 risk scoring, category attribution, unicode/base64/zero-width evasion unmasking, hard threshold blocking |
| **Data privacy & GDPR data minimisation**         | Presidio-based redaction runs *before* the model call; raw values never cross the boundary; only placeholders are ever sent out |
| **Application/API security**                      | API-key auth, per-client rate limiting, size caps, fail-closed validation, append-only auditable logging, TLS in the prod compose |
| **Polyglot engineering + testing discipline**     | FastAPI + Spring Boot + Vue/TS; pytest, mvn, Playwright E2E and a one-command verification script |
| **Realistic production concerns**                 | containerised deployment (dev + prod compose), healthchecks, Dockerfiles, backup/rotation runbook |

The threat model in [`docs/security-model.md`](docs/security-model.md) is informed
by the **OWASP LLM Top 10** and considers **EU AI Act** risk-management themes.
The mapping is non-exhaustive, states what is *not* mitigated, and is neither a
certification nor a claim of compliance.

## Features

- **Document validation microservice** — a Spring Boot service checks upload
  metadata (extension, declared content type, size, non-emptiness, path-traversal
  safety) and returns a structured result. The backend calls it before reading any
  file and **fails closed** if it is unavailable (`java-validator/`).
- **Prompt-injection defence** — a rule engine scores each request **0–100** with
  named categories, blocks at a configurable threshold, and unmasks evasion
  attempts (zero-width characters, unicode escapes, base64 payloads)
  (`services/guard_service.py`). Evaluated on a labelled 77-case synthetic corpus
  (`make eval-guard`): **98.1% injection recall (52/53)** and **8.3%
  false-positive rate (2/24 benign cases)** at threshold 40. This is an initial
  baseline measurement, not a production-scale benchmark.

  This is a small, synthetic baseline corpus. The threshold was evaluated on the
  same corpus, so results should be treated as an initial measurement rather than
  a guaranteed real-world performance figure. The benign set should be
  expanded—especially with realistic German contracts, invoices, HR documents,
  and encoded business content—before tuning the threshold further. See
  [`docs/guard-eval.md`](docs/guard-eval.md).

  The current guard is a deterministic first-line control. It is designed to catch
  common direct and obfuscated injection patterns, but novel paraphrases, indirect
  injections, and sophisticated semantic attacks may still evade it. A separately
  governed classifier and ongoing red-team evaluation would be required for
  stronger coverage.
- **PII redaction** — Microsoft Presidio detects `PERSON`, `EMAIL_ADDRESS`,
  `PHONE_NUMBER`, `CREDIT_CARD`, `IBAN_CODE` (plus a custom German IBAN pattern);
  each entity becomes a `[PII_TYPE_<id>]` placeholder.
- **Encrypted vault** — placeholder → original mappings are stored with Fernet
  (AES-128-CBC + HMAC) and never leave the backend.
- **Upload + text extraction** — `txt`, `md`, `pdf` (pypdf), `docx` (python-docx)
  are read **in memory only**; uploads are never written to disk.
- **Abuse protection** — per-client-IP rate limiting (`429` + `Retry-After`) and
  strict text/upload size limits before any model call.
- **Audit trail** — every processed, blocked, or rejected request appends a
  metadata-only record to `data/audit.log`.
- **Security dashboard** — Vue 3 UI with a live pipeline view, blocked-request
  panel, copy buttons, and a session event feed.

## Architecture

```mermaid
flowchart TB
    subgraph client [Browser]
        UI[Vue 3 dashboard]
    end
    subgraph edge [nginx]
        NX[proxy /api /health<br/>injects X-API-Key]
    end
    subgraph backend [FastAPI]
        RT[API routes + X-API-Key auth]
        EX[Extraction: pypdf / python-docx]
        GD[Injection guard 0-100]
        PI[Presidio redaction + Fernet vault]
        AU[JSONL audit log]
        VC[Validation client]
    end
    VAL[Java validator: Spring Boot]
    LLM[Gemini API]

    UI --> NX --> RT
    RT --> VC --> VAL
    RT --> EX --> GD --> PI --> LLM
    GD --> AU
    PI --> AU
    RT --> AU
```

## Project structure

```
backend/                       # FastAPI pipeline
  app/
    api/routes.py              # /process-document, /upload-document, /version
    core/config.py             # pydantic-settings
    core/auth.py               # X-API-Key dependency
    core/security.py           # Fernet key derivation
    services/guard_service.py  # injection scoring + evasion checks
    services/pii_service.py    # Presidio redaction
    services/extraction_service.py
    services/validation_service.py  # client for the Java service
    services/llm_service.py
    services/audit_service.py
  tests/                       # pytest suite
java-validator/                # Spring Boot validation microservice
  src/main/java/com/securedoc/validator/
  src/test/java/com/securedoc/validator/
frontend/                      # Vue 3 + TypeScript + Vite dashboard
docs/                          # architecture, security model, demo script, verification
scripts/smoke-test.sh          # end-to-end curl checks
scripts/verify-all.sh          # one-command verification (pytest + mvn + build + e2e)
Makefile
docker-compose.yml             # dev stack (nginx, backend, validator)
docker-compose.prod.yml        # production stack (TLS, restricted ports)
.env.production.example        # production secrets template
```

## Quick start

### Docker (whole stack)

```bash
export TOKEN_VAULT_KEY="$(openssl rand -base64 32)"
export SECUREDOC_API_KEY="$(openssl rand -hex 32)"
export GEMINI_API_KEY="your-key"        # optional
docker compose up --build
```

Frontend: `http://localhost:3002` · Backend: `http://localhost:8000` · Validator:
`http://localhost:8080`.

> **Port conflict?** The compose file maps the frontend to host port `3002`, since
> `3000` and `3001` are commonly taken (Gitea, Grafana, uptime-kuma). If `3002` is
> also in use, `docker compose up` fails with `bind: address already in use`; remap
> the frontend in [`docker-compose.yml`](docker-compose.yml) and open the new port:
>
> ```yaml
> ports: ["3003:80"]
> ```

The browser only ever talks to **nginx** on port 3002. nginx proxies `/api` and
`/health` to the backend and injects `X-API-Key` from `SECUREDOC_API_KEY` at
request time, so the key is **never built into the frontend bundle**. Backend and
validator are bound to `127.0.0.1` for local debugging only.

**Verify the stack** (Docker daemon required):

```bash
docker compose up --build -d
curl -s http://localhost:8000/health                 # {"status":"ok",...}
open http://localhost:8000/docs                       # OpenAPI docs
open http://localhost:3002                            # dashboard
make smoke                                            # end-to-end smoke test
make eval-guard                                       # offline injection-guard evaluation
make audit                                            # print the audit log
docker compose down
```

> Running the daemon on another host (via `DOCKER_HOST` or a `docker context` over
> SSH)? `make smoke`, `make audit`, and `scripts/verify-all.sh` run their checks
> **inside** the compose network, so they work even when the published ports are
> not reachable from your laptop.

`make smoke` checks health, public endpoints, the `401` on unauthenticated
requests, successful safe processing, absence of raw PII in the response, and that
an injection attempt is blocked with `400`.

### Local development

```bash
# Backend
cd backend
python3.12 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m spacy download en_core_web_lg
cp ../.env.example .env                # then edit values
./.venv/bin/uvicorn app.main:app --reload --port 8000

# Java validator (needs JDK 21 + Maven)
cd ../java-validator && mvn spring-boot:run

# Frontend
cd ../frontend && npm install
export SECUREDOC_API_KEY="your-key"    # dev proxy injects it server-side
npm run dev                            # http://localhost:5173
```

`GEMINI_API_KEY` is optional: without it the endpoint returns a graceful
`llm_unavailable` message after redaction, so the pipeline can be demonstrated
end-to-end without an external account.

`make help` lists every shortcut (`make backend-test`, `make java-test`,
`make frontend-build`, `make up`, `make logs`, `make smoke`, …).

## Configuration

All settings are read from the environment or `backend/.env`.

| Variable                    | Default                          | Purpose                                                     |
| --------------------------- | -------------------------------- | ----------------------------------------------------------- |
| `GEMINI_API_KEY`            | _(empty)_                        | Google Gemini API key; unset disables the LLM call.         |
| `GEMINI_MODEL`              | `gemini-3.8-flash`               | Model used for processing.                                  |
| `APP_ENV`                   | `development`                    | Environment label.                                          |
| `DATABASE_URL`              | `sqlite:///./data/securedoc.db`  | SQLite path.                                                |
| `AUDIT_LOG_PATH`            | `./data/audit.log`               | Append-only JSONL audit log.                                |
| `TOKEN_VAULT_KEY`           | _(empty)_                        | Fernet key or passphrase; **required** for redaction.       |
| `SECUREDOC_API_KEY`         | _(empty)_                        | API key for protected endpoints; **required** to serve them.|
| `INJECTION_BLOCK_THRESHOLD` | `40`                             | Risk score (0–100) at or above which a request is blocked.  |
| `JAVA_VALIDATOR_URL`        | `http://localhost:8080`          | Base URL of the validation service.                         |
| `MAX_UPLOAD_SIZE_MB`        | `5`                              | Maximum accepted document size.                             |
| `MAX_TEXT_CHARS`            | `20000`                          | Maximum text length for `/api/process-document`.            |
| `RATE_LIMIT_PER_MINUTE`     | `20`                             | Document requests allowed per client IP per minute (`429`). |

## API

All protected endpoints require the `X-API-Key` header.

### `POST /api/process-document`

```json
{ "text": "Email alice@example.com about IBAN DE89 3704 0044 0532 0130 00.", "task": "summarize" }
```

### `POST /api/upload-document`

`multipart/form-data` with `file` (`.txt`, `.md`, `.pdf`, `.docx`, ≤ 5 MB) and an
optional `task`. The file is validated, extracted in memory, then processed by the
same pipeline — it is never stored.

**200** — `{ task, filename, sanitized_preview, pii: { entity_count, entity_types, entities }, llm_output, audit_event_id, latency_ms }`

**400** — blocked by the guard (or rejected by the validator):

```json
{
  "message": "Request blocked by security policy",
  "reasons": ["instruction_override"],
  "categories": ["instruction_override"],
  "risk_level": "high",
  "score": 45,
  "audit_event_id": "..."
}
```

Other statuses: **401** missing/invalid key, **413** too large (text or file),
**415** unsupported/unreadable file, **429** rate limit exceeded (with
`Retry-After`), **503** validator unavailable.

### Utility endpoints

- `GET /health` — liveness probe with version.
- `GET /api/version` — app name and version.

## Tests

```bash
cd backend && ./.venv/bin/python -m pytest -v                        # Python
cd java-validator && mvn test                                        # Java
cd frontend && npm run build                                         # type-check + build
```

The pytest suite configures its own `TOKEN_VAULT_KEY` and `SECUREDOC_API_KEY`
via `setdefault` in `tests/conftest.py`, so it runs without environment setup —
and an explicitly exported value is honoured, so the auth tests always exercise
the key the app is actually configured with.

### End-to-end browser tests (Playwright)

Boots the Java validator, the FastAPI backend, and the Vite dev server, then
runs the full user journey in a real headless Chromium: safe-document
processing + PII redaction + audit trail, malicious-payload blocking, and the
upload flow. The suite runs **without a Gemini key** and asserts the graceful
"LLM unavailable" state instead of calling a model.

```bash
cd frontend
npx playwright install chromium   # once
JAVA_HOME=... npm run test:e2e    # JDK 21 required
npm run capture                   # regenerate the screenshots in docs/assets/
```

## Acknowledgements

- **PII detection/anonymisation** — [Microsoft Presidio](https://microsoft.github.io/presidio/).
- **Prompt-injection taxonomy** — informed by the [OWASP LLM Application
  Security Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
  (overflow attacks, indirect injection, prompt leakage) and EU AI Act
  risk-management themes.
- **Document validation microservice** — Spring Boot 3.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — components and request flow.
- [`docs/security-model.md`](docs/security-model.md) — threats, mitigations, limits.
- [`docs/demo-script.md`](docs/demo-script.md) — a five-minute demo walkthrough.
- [`docs/screenshot-checklist.md`](docs/screenshot-checklist.md) — shots to capture.
- [`docs/verification.md`](docs/verification.md) — release check results and the
  items that require a Docker daemon or a live Gemini key.
- [`DEPLOYMENT.md`](DEPLOYMENT.md) — production deployment: Vercel + Railway
  (managed) and a single host with Docker Compose + nginx, plus TLS, backup,
  rotation.
- [`docs/live-demo-checklist.md`](docs/live-demo-checklist.md) — live-demo
  safety and shutdown checklist.
