# Deploying SecureDoc AI

There are two deployment shapes, described below. **Option B** (a single host
with Docker Compose + nginx) is the reference and keeps everything on one
network. **Option A** splits the app across managed platforms: the Vue
frontend on **Vercel** and the FastAPI backend + Java validator on **Railway**.

- [Option A — Vercel (frontend) + Railway (backend + validator)](#option-a--vercel-frontend--railway-backend--validator)
- [Option B — single host with Docker Compose + nginx](#option-b--single-host-with-docker-compose--nginx)
- [Security checklist (before going live)](#6-security-checklist-before-going-live)

## Option A — Vercel (frontend) + Railway (backend + validator)

This split hosts the SPA and the API on separate origins. The browser only ever
talks to Vercel; a serverless proxy injects the API key so it never reaches the
client, and it forwards to the backend over HTTPS.

```
Browser ─▶ Vercel (Vue SPA + /api proxy) ─▶ Railway: FastAPI ─▶ Railway: Java validator
```

### A.1 Backend on Railway

1. Create a Railway service from this repo with **root directory `backend`**.
   Railway detects `backend/Dockerfile`. The image binds `0.0.0.0:$PORT`.
2. Add the validator as a second service (**root directory `java-validator`**,
   `java-validator/Dockerfile`). It reads `PORT` from the environment
   (`application.yml`).
3. Give the backend a **private** reference to the validator and set the
   backend's environment variables:

   | Variable                | Value                                                        |
   | ----------------------- | ------------------------------------------------------------ |
   | `APP_ENV`               | `production`                                                 |
   | `TOKEN_VAULT_KEY`       | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
   | `SECUREDOC_API_KEY`     | `python -c "import secrets; print(secrets.token_hex(24))"`   |
   | `GEMINI_API_KEY`        | Google Gemini key (optional but needed for real output)      |
   | `GEMINI_MODEL`          | `gemini-3.8-flash`                                           |
   | `JAVA_VALIDATOR_URL`    | `http://<validator-service>.railway.internal:8080`           |
   | `ALLOWED_CORS_ORIGINS`  | `https://<your-project>.vercel.app`                          |
   | `DATABASE_URL`          | `sqlite:////data/securedoc.db` (mount a Railway volume at `/data`) |
   | `AUDIT_LOG_PATH`        | `/data/audit.log`                                            |

4. Expose the backend with a **public domain** (Vercel must reach it). The
   validator stays private. `SECUREDOC_API_KEY` is the only thing protecting the
   public backend, so treat it as a secret and rotate it if exposed.

### A.2 Frontend on Vercel

1. Import the repo into Vercel with **root directory `frontend`**. Vercel uses
   `frontend/vercel.json` (Vite build, `dist` output, SPA rewrite).
2. Set the two **server-only** environment variables (see
   `frontend/.env.production.example`): `SECUREDOC_API_KEY` (same value as the
   backend) and `BACKEND_URL` (the Railway backend's public URL). Do not prefix
   them with `VITE_`.
3. `frontend/api/[[...path]].py` proxies `/api/process-document`,
   `/api/upload-document`, and `/api/version` and injects `X-API-Key`.

### A.3 Known limitation

The Vercel **Hobby** plan caps a serverless function at **10s** and a request
body at **~4.5 MB** — both below this app's needs (Gemini calls run ~11–14s and
uploads go to 5 MB). On Hobby, LLM-backed and larger-upload requests will fail
at the edge; use a Pro plan or send those requests to the backend directly. See
`frontend/api/README.md`.

### A.4 Verify (no deploy performed here)

```bash
curl -sf https://<backend>.up.railway.app/health | python -m json.tool
curl -sf https://<frontend>.vercel.app/api/version | python -m json.tool
```

Do **not** run `vercel deploy` / `railway up` from an agent session; the buttons
above belong to the account owner.

## Option B — single host with Docker Compose + nginx

## 1. Prerequisites

- Docker Engine + Compose v2 on the host.
- A registered domain pointing at the server (for TLS).
- To use the LLM, a Google Gemini API key. Without one the app still works:
  it returns sanitized text with "LLM provider is not configured".

## 2. Prepare the environment

```bash
cp .env.production.example .env
# fill in real values, then generate keys:
python -c "import secrets; print(secrets.token_urlsafe(32))"   # -> TOKEN_VAULT_KEY
python -c "import secrets; print(secrets.token_hex(24))"       # -> SECUREDOC_API_KEY
```

| Variable            | Purpose                                                        |
| ------------------- | -------------------------------------------------------------- |
| `TOKEN_VAULT_KEY`   | Fernet key that encrypts PII placeholders in transit/responses |
| `SECUREDOC_API_KEY` | Shared header key; nginx injects it, backend validates it      |
| `GEMINI_API_KEY`    | Optional; enables the model step                               |
| `PUBLIC_ORIGIN`     | Public hostname, e.g. `securedoc.example.com`                  |

## 3. TLS certificates

Place the certificate and key at `./certs/server.crt` and `./certs/server.key`
(or point `CERTS_DIR` elsewhere), then:

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

With a DNS A record already set, certificates can be issued automatically:

```bash
docker run --rm -it \
  -v "$(pwd)/certs:/etc/letsencrypt" \
  -v "$(pwd)/certbot-webroot:/var/www/certbot" \
  -p 80:80 \
  certbot/certbot certonly --standalone \
  -d securedoc.example.com \
  --email you@example.com --agree-tos --no-eff-email
# copy /etc/letsencrypt/live/<domain>/{fullchain.pem,privkey.pem} into ./certs as server.crt/server.key
```

Renew before expiry (certbot adds a cron/systemd timer for this).

## 4. Verify the deployment

```bash
curl -sf https://securedoc.example.com/health | python -m json.tool     # {"status":"ok",...}
curl -sf -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $SECUREDOC_API_KEY" \
  https://securedoc.example.com/api/process-document \
  -d '{"text":"hello","task":"summarize"}'                                # 200
```

## 5. Operational notes

- **Persistence.** `securedoc_data` volume holds the SQLite audit DB and the
  append-only audit log. Back it up (`docker run --rm -v securedoc_data:/d -v
  "$PWD":/b alpine tar czf /b/backup.tgz -C /d .`); only placeholders and
  hashed identities are stored — no raw document content.
- **Key rotation.** Rotating `TOKEN_VAULT_KEY` is safe at any time: nothing is
  encrypted at rest, so old ciphertext never needs re-encryption. Rotate
  `SECUREDOC_API_KEY` by updating `.env` and restarting the stack.
- **Logs.** JSON structured logs are written to `stdout`; the audit trail to the
  mounted volume. Ship both to your log aggregator.
- **Rate limiting.** Default 20 document requests/minute per client IP
  (`RATE_LIMIT_PER_MINUTE`). Tune for your user base.
- **Horizontal scaling.** The backend is stateless (SQLite is single-writer); to
  scale, move the audit DB to a networked store or run multiple readers behind a
  single writer.

## 6. Security checklist (before going live)

- [ ] `.env` exists, is chmod 600, and is not in git (`git check-ignore .env`)
- [ ] Certs are fresh; HTTP redirects to HTTPS
- [ ] `GEMINI_API_KEY` is a restricted key (no billing abuse exposure)
- [ ] DNS + TLS verified via the curl checks above
- [ ] Auditing: check the audit log volume actually grows after requests
- [ ] Rate limiter review: set `RATE_LIMIT_PER_MINUTE` to an expected ceiling
- [ ] Backups of `securedoc_data` scheduled; restore tested