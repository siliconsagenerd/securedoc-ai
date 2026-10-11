# Security Model

SecureDoc AI is a privacy layer between a user's document and an external LLM.
This document lists what it protects against, how, and where the guarantees stop.

## Threat model

| Threat                                       | Mitigation                                                                                      |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| **Prompt injection** ("ignore previous…")    | `GuardService` scores input 0–100 with named categories and blocks at `INJECTION_BLOCK_THRESHOLD`. |
| **Obfuscated injection** (zero-width, escapes, base64) | Guard strips invisible characters and decodes escaped/base64 payloads before matching. |
| **Unauthenticated use**                      | Protected endpoints require `X-API-Key`; missing/empty config fails closed; comparison is constant-time. |
| **Malicious uploads**                        | The Java validator checks extension, content type, size, and filename safety before extraction. |
| **PII leakage to the LLM provider**          | Presidio redaction replaces entities with opaque placeholders before transmission.               |
| **PII leakage via logs**                     | Audit records store metadata only; raw text and entity values are never written.                 |
| **PII leakage via API response**             | Responses contain placeholders, not original values; rehydration is internal-only.              |
| **PII written to disk by upload**            | Uploaded files are extracted in memory and never persisted.                                      |
| **Vault disclosure (file at rest)**          | Mappings are Fernet-encrypted; the key lives in `TOKEN_VAULT_KEY`, never in the repo.            |
| **Accidental secret commits**                | `.env` gitignored; `.env.example` holds placeholders only.                                        |
| **Oversized payloads / DoS**                 | `MAX_UPLOAD_SIZE_MB` enforced both at the schema and by the validator.                           |

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

## Limitations

- **Regex guard, not a model** — novel or obfuscated injections can evade the
  pattern set. The guard is defense-in-depth, not a proof.
- **Single static API key** — `SECUREDOC_API_KEY` is one shared secret; there is
  no per-user identity, rotation, or rate limiting yet.
- **Key shipped to the browser** — the frontend sends `VITE_API_KEY`, which is
  compiled into the bundle. For public deployments keep the key server-side
  (proxy or BFF) and treat the shipped value as non-secret.
- **Validator checks metadata, not content** — the Java service inspects declared
  type, extension, and size; it does not scan file contents for malware.
- **Detection is statistical** — Presidio can miss unusual PII formats and can
  produce false positives. The custom German IBAN recognizer covers the common
  format only.
- **Key management is operator-provided** — the app does not rotate or persist
  `TOKEN_VAULT_KEY`; a lost key makes existing vault entries unrecoverable.
- **Third-party provider** — Google Gemini receives redacted text and is subject
  to its own data-handling terms.
