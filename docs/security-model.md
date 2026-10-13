# Security Model

SecureDoc AI is a privacy layer between a user's document and an external LLM.
This document lists what it protects against, how, and where the guarantees stop.

## Threat model

| Threat                                       | Mitigation                                                                                      |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| **Prompt injection** ("ignore previous…")    | `GuardService` scores input 0–100 with named categories and blocks at `INJECTION_BLOCK_THRESHOLD`. |
| **Obfuscated injection** (zero-width, escapes, base64) | Guard strips invisible characters and decodes escaped/base64 payloads before matching. |
| **Unauthenticated use**                      | Protected endpoints require `X-API-Key`; the proxy injects it so the browser never holds it; missing/empty config fails closed; comparison is constant-time and fails closed on malformed (non-ASCII) keys. |
| **Malicious uploads**                        | The Java validator checks extension, content type, size, and filename safety before extraction. |
| **PII leakage to the LLM provider**          | Presidio redaction replaces entities with opaque placeholders before transmission.               |
| **PII leakage via logs**                     | Audit records store metadata only; raw text and entity values are never written.                 |
| **PII leakage via API response**             | Responses contain placeholders, not original values; rehydration is internal-only.              |
| **PII written to disk by upload**            | Uploaded files are extracted in memory and never persisted.                                      |
| **Vault disclosure (file at rest)**          | Mappings are Fernet-encrypted; the key lives in `TOKEN_VAULT_KEY`, never in the repo.            |
| **Accidental secret commits**                | `.env` gitignored; `.env.example` holds placeholders only.                                        |
| **Oversized payloads / DoS**                 | `MAX_UPLOAD_SIZE_MB` enforced both at the schema and by the validator.                           |
| **Request flooding / brute force**           | In-memory fixed-window limiter keyed on the caller's IP; per-route `RATE_LIMIT_PER_MINUTE` returns `429` with `Retry-After`. |
| **Rate-limit evasion via spoofed headers**   | The limiting identity is taken from `X-Real-IP`, which our nginx sets to `$remote_addr`. nginx **overwrites** (never appends) `X-Forwarded-For`, and the limiter only ever reads the proxy-added value — a rotated client-supplied `X-Forwarded-For` cannot mint new buckets. |

## Cryptographic details

- Algorithm: Fernet (AES-128-CBC with HMAC-SHA256 authentication).
- Key derivation: a valid Fernet key is used as-is; any other value is hashed to
  32 bytes with SHA-256 and base64url-encoded. This lets operators use a
  passphrase or a generated key.
- Scope: each placeholder value is encrypted independently, so a single mapping
  can be decrypted without exposing the rest of the vault.

## Audit trail

Each event (processed / blocked / error) appends one JSON line with: timestamp
(UTC ISO-8601), event id, action, task, risk level, risk score, entity type
counts, outcome, and latency. The field whitelist in `audit_service.py` prevents accidental
inclusion of free-form text.

## Guard evaluation

`backend/evals/run.py` runs a labelled corpus of 77 cases
(`backend/evals/corpus.jsonl`: 53 attacks + 24 benign controls) through
`GuardService` **offline** — no LLM calls, so it is free and reproducible — and
writes `docs/guard-eval.md`. Run it with `make eval-guard`.

Result after hardening (threshold 40): **98.1% attack detection (52/53)** and
**8.3% false-positive rate (2/24)**. The same corpus scored **39.6% detection
before** hardening; the rule set was extended for paraphrase overrides,
non-English instructions, role-play jailbreaks, exfiltration to an external
address, chat control tokens, and letter-spacing evasion.

Known misses (documented, not fixed): hyphenated keyword runs
(`Ignore-all-previous-instructions`) and two benign phrasings that read like
overrides (`docs/guard-eval.md`). Closing the false positives needs a
context-aware second stage — the LLM classifier the module docstring
anticipates — not more patterns.

## Availability and upstream failures

The LLM call is bounded: the Gemini client is created with a 60s request timeout
and a single attempt (`llm_service._REQUEST_TIMEOUT_MS`), and nginx waits up to
90s (`proxy_read_timeout`) before giving up. Without both, a provider 5xx/429
made the SDK retry with backoff for minutes while nginx's 60s default surfaced a
`504 Gateway Time-out` to the browser even though the backend eventually
succeeded. When the model is unavailable the call now fails fast and the API
still returns `200` with a clear fallback message, the sanitized text, and no
data sent externally.

## Limitations

- **Regex guard, not a model** — novel or obfuscated injections can evade the
  pattern set (measured in [Guard evaluation](#guard-evaluation)). The guard is
  defense-in-depth, not a proof.
- **Single static API key** — `SECUREDOC_API_KEY` is one shared secret; there is
  no per-user identity or key rotation (rate limiting is keyed on client IP, not
  on a user).
- **Key is server-side only** — the browser talks to nginx (or the Vite dev
  proxy), which injects `X-API-Key` from `SECUREDOC_API_KEY`. The key is not in
  the frontend bundle; anyone with shell access to the proxy host can still read
  it, so protect that host.
- **Validator checks metadata, not content** — the Java service inspects declared
  type, extension, and size; it does not scan file contents for malware.
- **Detection is statistical** — Presidio can miss unusual PII formats and can
  produce false positives. The custom German IBAN recognizer covers the common
  format only.
- **Key management is operator-provided** — the app does not rotate or persist
  `TOKEN_VAULT_KEY`; a lost key makes existing vault entries unrecoverable.
- **Rate limiter is in-memory and per-process** — buckets live in the process
  and reset on restart; behind multiple replicas each would keep its own counts.
  A shared store (e.g. Redis) is needed to limit across replicas.
- **Upload size is checked before decompression only** — `MAX_UPLOAD_SIZE_MB`
  bounds the request body, but extraction expands in memory: a `.docx` (a zip)
  or a many-page PDF can expand far beyond its compressed size. No expansion or
  page-count guard yet.
- **Third-party provider** — Google Gemini receives redacted text and is subject
  to its own data-handling terms.
