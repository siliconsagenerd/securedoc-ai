# Live demo — safety and shutdown checklist

Run the demo from the repo with the stack up on the remote Docker host. Nothing
below publishes the app or exposes it to the public internet.

## Vercel Hobby limitation

Vercel Hobby is not recommended for a public live demo of SecureDoc AI.

Gemini processing may take 11–14 seconds, while Vercel Hobby serverless functions have an approximately 10-second execution limit. The application also supports uploads up to 5 MB, while Vercel Hobby has an approximately 4.5 MB request-body limit.

For a hosted demo, deploy the Vue dashboard, FastAPI backend, and Java validator on a container platform that supports long-running services, such as Railway, Render, Fly.io, or a VPS.

## Recommended hosted demo architecture

```text
Recommended hosted demo:
Browser → Railway static hosting or Vercel frontend → Railway FastAPI backend → Railway Java validator → Gemini API

All secrets remain server-side. The Java validator remains private. The backend is not exposed directly to the browser.
```

The checklist below uses the container stack (`make up`, nginx on `:3002`),
which is a long-running service — the recommended shape for a full live demo.
Do **not** run a public demo through the Vercel Hobby proxy: it is only suitable
for a small, low-latency, text-only case, not the full upload workflow or normal
Gemini response times (11–14 s).

## Before the demo

- [ ] `git status` is clean; on `main` at the expected commit.
- [ ] `.env` exists (never committed) with `TOKEN_VAULT_KEY`,
      `SECUREDOC_API_KEY`, `GEMINI_API_KEY`, `GEMINI_MODEL=gemini-3.8-flash`.
- [ ] Stack is up: `make up` (frontend on `http://<host>:3002`).
- [ ] Health is green: `make smoke` → 7/7 checks pass.
- [ ] Beacons are green in the header ("API online").

## During the demo

- [ ] **Safe sample** → redacted preview, placeholders only, model summary.
      Confirm no raw name/email/IBAN/phone appears in the "Sanitized payload".
- [ ] **Injection sample** → "Request blocked", high risk, no model call.
- [ ] **Upload** `data/samples/invoice_sample.txt` → validator accepts, same
      redaction + model path.
- [ ] Point at the Live telemetry ledger and the audit event id on each result.
- [ ] Say "prompt-injection recall", "benign pass rate", and "false-positive
      rate" — not "accuracy". Cite `docs/guard-eval.md`.

## Never show or say

- [ ] Do not open `.env`, the audit log, or any terminal holding a key.
- [ ] Do not read the API key aloud or share the screen with it visible.
- [ ] Do not claim PII is "never stored" beyond what's true: placeholders and
      hashed identities are stored in the audit DB/log; raw content is not.

## After the demo — shut down

```bash
make down          # stop the stack
```

- [ ] Confirm containers stopped: `docker compose ps` shows none running.
- [ ] If anything may have been exposed, rotate `SECUREDOC_API_KEY` and
      `TOKEN_VAULT_KEY`, restart, re-run `make smoke`.
- [ ] Archive the audit log if a reviewer asked for evidence.
