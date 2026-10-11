# Deploying SecureDoc AI

Production deployment uses the same three containers as local development, with a
TLS-terminating nginx edge on ports 80/443. The API key is injected by nginx as a
request header and is **never** baked into the frontend bundle.

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