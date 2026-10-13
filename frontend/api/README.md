# Vercel serverless API proxy

`[[...path]].py` is a dependency-free proxy that sits between the browser and
the FastAPI backend on Railway. It exists so the **shared API key never reaches
the browser**: the SPA calls same-origin `/api/*`, and this function adds the
`X-API-Key` header server-side from `SECUREDOC_API_KEY`.

## Allowed routes

| Method | Path                     | Purpose                    |
| ------ | ------------------------ | -------------------------- |
| POST   | `/api/process-document`  | Text document pipeline     |
| POST   | `/api/upload-document`   | File upload pipeline       |
| GET    | `/api/version`           | Health/version probe       |

Any other path or method returns `404` without contacting the backend. The
three document endpoints are themselves protected by the backend's API-key
check and in-memory rate limiter.

## Environment variables (Vercel, server-only — never prefixed `VITE_`)

| Variable             | Purpose                                              |
| -------------------- | ---------------------------------------------------- |
| `SECUREDOC_API_KEY`  | Injected as `X-API-Key`; must match the backend      |
| `BACKEND_URL`        | Public Railway base URL, e.g. `https://…up.railway.app` |

## Behaviour and limits

- Request bodies are forwarded untouched and **never logged**.
- Bodies larger than 6 MB are rejected with `413` before the backend is called.
- Upstream calls time out after 55s; failures return `502` with no internal
  detail.
- `maxDuration` is set to 60s in `../vercel.json`.

### Known limitation — Vercel Hobby plan

- **Duration.** Hobby caps a function at **10s**; real Gemini calls have been
  observed at **~11–14s**. On Hobby, LLM-backed requests will time out. Use a
  Pro plan (60s) or call the Railway backend directly.
- **Body size.** Vercel rejects request bodies over **~4.5 MB** at the platform
  edge, below the app's 5 MB upload limit. Larger uploads must go to the backend
  directly.

Because of the above, this proxy is best treated as a **demo-grade** edge for
short requests. For production, either upgrade the Vercel plan or accept that
uploads/long generations may fail here.

## Local check

```bash
python frontend/api/\[\[...path\]\].py   # runs the routing self-check
```
