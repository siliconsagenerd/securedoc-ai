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

### When the Vercel proxy is still fine

The proxy above is still usable for a **small, low-latency, text-only** demo:
short `/api/process-document` calls that return well under 10 seconds and no file
uploads. It is **not** appropriate for the full upload workflow (up to 5 MB) or
for normal Gemini response times (11–14 s) on the Hobby plan — those requests
will be cut off by the platform. For anything beyond that narrow case, host the
frontend and backend together on a long-running container platform.

## Local check

```bash
python frontend/api/\[\[...path\]\].py   # runs the routing self-check
```
