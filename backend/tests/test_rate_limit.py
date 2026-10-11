from app.core.rate_limit import rate_limiter


def _body(text: str) -> dict:
    return {"text": text, "task": "summarize"}


def test_rate_limit_triggers_429_with_retry_after(monkeypatch, client):
    monkeypatch.setattr(rate_limiter, "limit", 2)
    rate_limiter.reset()

    try:
        assert client.post("/api/process-document", json=_body("one")).status_code == 200
        assert client.post("/api/process-document", json=_body("two")).status_code == 200
        blocked = client.post("/api/process-document", json=_body("three"))
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) >= 1
    finally:
        rate_limiter.reset()


def test_valid_requests_pass_below_the_limit(monkeypatch, client):
    monkeypatch.setattr(rate_limiter, "limit", 10)
    rate_limiter.reset()

    try:
        for _ in range(3):
            response = client.post("/api/process-document", json=_body("hello"))
            assert response.status_code == 200
    finally:
        rate_limiter.reset()


def test_oversized_text_rejected(monkeypatch, client):
    monkeypatch.setattr(rate_limiter, "limit", 100)
    rate_limiter.reset()

    try:
        too_large = "a" * 20_001
        response = client.post("/api/process-document", json=_body(too_large))
        assert response.status_code == 413
    finally:
        rate_limiter.reset()


def test_oversized_upload_rejected(monkeypatch, client):
    monkeypatch.setattr(rate_limiter, "limit", 100)
    rate_limiter.reset()

    try:
        response = client.post(
            "/api/upload-document",
            files={"file": ("big.txt", b"a" * (5 * 1024 * 1024 + 1), "text/plain")},
        )
        assert response.status_code == 413
    finally:
        rate_limiter.reset()