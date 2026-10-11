# SecureDoc AI

GDPR-oriented security layer for LLM-based document processing.
Sensitive data is **redacted and encrypted locally** before any text is sent to an
external model, prompt-injection attempts are blocked, and every decision is written
to an append-only audit log.

```
User → Vue dashboard → FastAPI → ┌ guard (injection check)
                                 ├ PII redaction + encrypted token vault
                                 ├ Gemini API (sanitized text only)
                                 └ audit log (JSONL)
```

## Features

- **Prompt-injection defense** — regex-based guard scores each request and blocks
  high-risk input before it reaches the model (`services/guard_service.py`).
- **PII redaction** — Microsoft Presidio detects `PERSON`, `EMAIL_ADDRESS`,
  `PHONE_NUMBER`, `CREDIT_CARD`, `IBAN_CODE` (plus a custom German IBAN pattern);
  each entity is replaced with a `[PII_TYPE_<id>]` placeholder.
- **Encrypted vault** — placeholder → original value mappings are stored with
  Fernet (AES-128-CBC + HMAC). Raw values never leave the process boundary.
- **Audit trail** — every processed or blocked request appends a metadata-only
  record to `data/audit.log` (no raw document text).
- **Security telemetry dashboard** — Vue 3 UI showing the sanitized payload, the
  model output, and a live event feed of processed/blocked requests.

## Project structure

```
backend/
  app/
    api/routes.py            # HTTP endpoints
    core/config.py           # settings (pydantic-settings)
    core/security.py         # Fernet key derivation + encrypt/decrypt
    db/database.py           # stdlib sqlite3 helper
    schemas/document.py      # request/response models
    services/guard_service.py
    services/pii_service.py
    services/llm_service.py
    services/audit_service.py
    main.py                  # FastAPI app
  tests/                     # pytest suite
frontend/                    # Vue 3 + TypeScript + Vite dashboard
docs/                        # architecture + security model
data/                        # runtime (db, audit log) — gitignored
docker-compose.yml
```

## Quick start (local)

### Backend

```bash
cd backend
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m spacy download en_core_web_lg
cp ../.env.example .env          # then edit values
./.venv/bin/uvicorn app.main:app --reload --port 8000
```

The API is available at `http://127.0.0.1:8000` (interactive docs at `/docs`).
`GEMINI_API_KEY` is optional for local runs — without it the endpoint returns a
graceful `llm_unavailable` message after redaction so the pipeline can be tested.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env             # VITE_API_BASE_URL=http://127.0.0.1:8000
npm run dev                      # http://localhost:5173
```

### Docker

```bash
export TOKEN_VAULT_KEY="$(openssl rand -base64 32)"
export GEMINI_API_KEY="your-key"        # optional
docker compose up --build
```

Frontend: `http://localhost:3000` · Backend: `http://localhost:8000`.
Nginx proxies `/api` and `/health` to the backend so the browser stays same-origin.

## Configuration

All settings are read from the environment or `backend/.env`.

| Variable             | Default                          | Purpose                                              |
| -------------------- | -------------------------------- | ---------------------------------------------------- |
| `GEMINI_API_KEY`     | _(empty)_                        | Google Gemini API key; unset disables the LLM call.  |
| `GEMINI_MODEL`       | `gemini-2.0-flash`               | Model used for processing.                           |
| `APP_ENV`            | `development`                    | Environment label.                                   |
| `DATABASE_URL`       | `sqlite:///./data/securedoc.db`  | SQLite path.                                         |
| `AUDIT_LOG_PATH`     | `./data/audit.log`               | Append-only JSONL audit log.                         |
| `TOKEN_VAULT_KEY`    | _(empty)_                        | Fernet key or passphrase; **required** for redaction.|
| `MAX_UPLOAD_SIZE_MB` | `5`                              | Maximum accepted document size.                      |

## API

### `POST /api/process-document`

```json
{ "text": "Email alice@example.com about IBAN DE89 3704 0044 0532 0130 00.", "task": "summarize" }
```

`task` is one of `summarize`, `extract_fields`, `classify_document`.

**200** — `{ task, sanitized_preview, pii: { entity_count, entity_types, entities }, llm_output, audit_event_id, latency_ms }`

**400** — blocked by the guard:

```json
{ "message": "Request blocked by security policy", "reasons": ["instruction_override"], "risk_level": "high", "audit_event_id": "..." }
```

### Other

- `GET /health` — liveness probe with version.
- `GET /api/version` — app name and version.

## Tests

```bash
cd backend
TOKEN_VAULT_KEY=test ./.venv/bin/python -m pytest -v
```

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — components and request flow.
- [`docs/security-model.md`](docs/security-model.md) — threats, mitigations, limits.
