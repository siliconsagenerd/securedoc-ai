# Screenshot checklist

Capture these for the README, CV, or LinkedIn post. Use a wide window (≈1280px)
and the same sample data so the shots tell one story.

| # | Shot | What to show | Why it matters |
| - | ---- | ------------ | -------------- |
| 1 | Dashboard, empty | Header, **API online**, input card, pipeline chips | First impression / hero image |
| 2 | Safe sample processed | **Privacy shield** with placeholders + model output | Core value: redaction |
| 3 | Sanitized payload zoom | `[EMAIL_ADDRESS_…]`, `[IBAN_CODE_…]` in the preview | Proof no raw PII leaves |
| 4 | Injection blocked | **Request blocked** panel with score + categories | The security story |
| 5 | Pipeline close-up | Chips ending at **Guard = blocked** | Visual of the blocked path |
| 6 | File upload | Chosen-file chip before upload | Shows upload + validation |
| 7 | Upload result | Filename shown, redaction applied | Validation → processing flow |
| 8 | Security telemetry | Mixed processed / blocked feed | Session-level visibility |
| 9 | `docker compose ps` | backend, frontend, java-validator all **healthy** | Runs as a real stack |
| 10 | `curl /health` + `401` | `{"status":"ok"}` and an unauthenticated `401` | API discipline + auth |

## Naming

`securedoc-01-dashboard.png`, `securedoc-02-redaction.png`, … keeps them ordered.

## Tips

- Dark terminal + dark UI look consistent; keep the browser zoom at 100%.
- Blur or avoid any real keys (`TOKEN_VAULT_KEY`, `SECUREDOC_API_KEY`) before posting.
- For a GIF: record steps 2 → 4 of the demo script; it is under 20 seconds.
