# Architecture

## Components

| Layer      | Module                                   | Responsibility                                                  |
| ---------- | ---------------------------------------- | ---------------------------------------------------------------- |
| API        | `app/main.py`, `app/api/routes.py`       | HTTP surface, CORS, request orchestration, shared pipeline.       |
| Auth       | `app/core/auth.py`                       | `X-API-Key` dependency; fail-closed, constant-time comparison.    |
| Schema     | `app/schemas/document.py`                | Pydantic request/response contracts.                             |
| Guard      | `app/services/guard_service.py`          | Injection scoring 0–100, categories, block decisions, evasion.    |
| Privacy    | `app/services/pii_service.py`            | Presidio detection, placeholder substitution, token vault.        |
| Extraction | `app/services/extraction_service.py`     | In-memory `txt`/`md`/`pdf`/`docx` text extraction.                |
| Validate   | `app/services/validation_service.py`     | Client for the Java validator; fails closed on error.            |
| Crypto     | `app/core/security.py`                   | Fernet key derivation and encrypt/decrypt.                       |
| LLM        | `app/services/llm_service.py`            | Google Gemini client; task-specific prompts.                     |
| Audit      | `app/services/audit_service.py`          | Append-only JSONL event log.                                     |
| Config     | `app/core/config.py`                     | Environment-driven settings.                                     |
| UI         | `frontend/src/*`                         | Vue dashboard, API client, pipeline view, telemetry feed.        |
| Validator  | `java-validator/` (Spring Boot 3, Java 21)| Metadata validation microservice (`POST /api/v1/validate`).     |

## Request flow

Both endpoints end in the same shared pipeline (`_run_pipeline`).

### `POST /api/process-document`

1. **Authenticate** — `require_api_key` rejects missing/invalid keys with `401`.
2. **Validate** — size and `task` are checked by the request schema.
3. **Guard** — `GuardService.inspect` strips invisible characters, decodes
   unicode escapes and base64 payloads, then runs pattern rules and sums
   category points into a risk score (0–100). Score ≥
   `INJECTION_BLOCK_THRESHOLD` → `400` + audit `blocked` event; raw text is not
   logged.
4. **Redact** — `PIIService.redact`:
   - Presidio analyzes the text (spaCy `en_core_web_lg` + custom German IBAN
     recognizer).
   - A custom anonymizer operator replaces each entity with
     `[PII_<TYPE>_<10-hex>]` and stores `placeholder -> Fernet(original)`.
5. **Call model** — only `sanitized_text` is sent to Gemini.
   Missing key → graceful `llm_unavailable` result.
6. **Audit** — an outcome record (status, risk, score, entity types, latency)
   is appended to the JSONL log; never raw values.
7. **Respond** — sanitized preview, PII summary, model output, audit id, latency.

### `POST /api/upload-document`

`multipart/form-data`: after authentication and a size pre-check (`413`), the
upload's metadata (extension, content type, size, filename safety) is sent to the
**Java validator**. On rejection → `400`; if the validator is unreachable → `503`
(fail closed). The accepted file is extracted in memory (`415` on failure) and
then flows through steps 3–7 above. The file is never written to disk.

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
