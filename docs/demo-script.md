# Demo script (≈5 minutes)

A walkthrough that shows validation, redaction, injection defence, and audit in
one pass. Assumes the Docker stack (or local services) is running and the
dashboard is open at `http://localhost:3000`.

## 0. Setup (before the audience arrives)

```bash
export TOKEN_VAULT_KEY="$(openssl rand -base64 32)"
export SECUREDOC_API_KEY="$(openssl rand -hex 32)"
export GEMINI_API_KEY="your-key"      # optional
docker compose up --build -d
```

Open the dashboard and confirm the header shows **API online**.

## 1. The problem (30s)

"Teams paste sensitive documents into LLM tools. That sends raw personal data to a
third party. SecureDoc AI redacts and encrypts it locally first — the model only
ever sees placeholders."

## 2. Happy path — redaction (90s)

1. Click **Safe sample**.
2. Click **Process securely**.
3. Walk the **Pipeline** chips: Validate → Guard → Redact → Model → Audit.
4. Point at **Privacy shield**: the sanitized payload shows `[EMAIL_ADDRESS_…]`,
   `[PERSON_…]`, `[IBAN_CODE_…]` instead of the real values.
5. Mention: "The model output never contained `alice.johnson@example.com`."
6. Click **Copy** on the sanitized payload to show what is actually transmitted.

## 3. Security — injection blocked (60s)

1. Click **Injection sample**.
2. Click **Process securely**.
3. The **Request blocked** panel appears: risk `high`, a `0–100` score, threat
   **categories**, and the triggering rules.
4. Say: "Nothing was sent to the model and nothing was stored."

## 4. Upload + Java validation (60s)

1. Drag or choose `data/samples/invoice_sample.txt`.
2. Click **Upload & process**.
3. Note the file is validated by the separate **Java** service, extracted in
   memory, then redacted — it is never written to disk.
4. Optional: try a `.zip` to show the **415 / rejected** path.

## 5. Audit trail (30s)

```bash
make audit          # or: cat data/audit.log | tail
```

Show that events are metadata-only: action, status, risk level, entity types,
model, latency — **no raw document text**.

## 6. Wrap-up (30s)

- "Three independent layers: metadata validation, injection scoring, PII
  redaction — each can refuse a request."
- "Everything runs with one `docker compose up`."
- Point to the README architecture diagram and the test suites.
