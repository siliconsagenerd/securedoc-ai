# Architecture

## Components

| Layer    | Module                              | Responsibility                                              |
| -------- | ----------------------------------- | ----------------------------------------------------------- |
| API      | `app/main.py`, `app/api/routes.py`  | HTTP surface, CORS, request orchestration.                  |
| Schema   | `app/schemas/document.py`           | Pydantic request/response contracts.                        |
| Guard    | `app/services/guard_service.py`     | Injection/abuse scoring, block decisions.                   |
| Privacy  | `app/services/pii_service.py`       | Presidio detection, placeholder substitution, token vault.  |
| Crypto   | `app/core/security.py`              | Fernet key derivation and encrypt/decrypt.                  |
| LLM      | `app/services/llm_service.py`       | Google Gemini client; task-specific prompts.                |
| Audit    | `app/services/audit_service.py`     | Append-only JSONL event log.                                |
| Config   | `app/core/config.py`                | Environment-driven settings.                                |
| UI       | `frontend/src/*`                    | Vue dashboard, API client, telemetry feed.                  |

## Request flow — `POST /api/process-document`

1. **Validate** — size and `task` are checked by the request schema.
2. **Guard** — `GuardService.inspect` runs pattern rules and returns a
   `GuardVerdict`. High risk → `400` + audit `blocked` event; raw text is not
   logged.
3. **Redact** — `PIIService.redact`:
   - Presidio analyzes the text (spaCy `en_core_web_lg` + custom German IBAN
     recognizer).
   - A custom anonymizer operator replaces each entity with
     `[PII_<TYPE>_<10-hex>]` and stores `placeholder -> Fernet(original)`.
4. **Call model** — only `sanitized_text` is sent to Gemini.
   Missing key → graceful `llm_unavailable` result.
5. **Audit** — an `LLMService`/outcome record is appended to the JSONL log
   (entity types and counts, never raw values).
6. **Respond** — sanitized preview, PII summary, model output, audit id, latency.

## Data at rest

- `data/securedoc.db` — optional structured storage (stdlib `sqlite3`).
- `data/audit.log` — append-only JSONL, one event per line.
- `data/*` is gitignored and mounted as a volume in Docker.

## Key design decisions

- **No ORM** — the audit path is a JSONL file; structured storage uses stdlib
  `sqlite3`, avoiding a heavyweight dependency.
- **Placeholders are returned, not rehydrated values** — the public API never
  echoes raw PII. `PIIService.rehydrate` exists for controlled, server-side use.
- **Local-first** — redaction and encryption happen in-process; only redacted
  text crosses the network boundary.
