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


def test_rotating_x_forwarded_for_prefix_cannot_bypass_limit(monkeypatch, client):
    """A client-controlled X-Forwarded-For prefix must not mint new buckets.

    Our nginx appends the real peer, so only the right-most entry is trusted.
    Rotating the spoofable prefix must still hit the one shared bucket.
    """
    monkeypatch.setattr(rate_limiter, "limit", 2)
    rate_limiter.reset()

    try:
        for i in range(2):
            response = client.post(
                "/api/process-document",
                json=_body("one"),
                headers={"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.9"},
            )
            assert response.status_code == 200

        blocked = client.post(
            "/api/process-document",
            json=_body("three"),
            headers={"X-Forwarded-For": "10.0.0.99, 203.0.113.9"},
        )
        assert blocked.status_code == 429
    finally:
        rate_limiter.reset()


def test_x_real_ip_is_authoritative_over_x_forwarded_for(monkeypatch, client):
    """X-Real-IP (set by our proxy) identifies the caller even if XFF is rotated."""
    monkeypatch.setattr(rate_limiter, "limit", 2)
    rate_limiter.reset()

    try:
        for i in range(2):
            response = client.post(
                "/api/process-document",
                json=_body("one"),
                headers={"X-Real-IP": "203.0.113.9", "X-Forwarded-For": f"10.0.0.{i}"},
            )
            assert response.status_code == 200

        blocked = client.post(
            "/api/process-document",
            json=_body("three"),
            headers={"X-Real-IP": "203.0.113.9", "X-Forwarded-For": "10.0.0.99"},
        )
        assert blocked.status_code == 429
    finally:
        rate_limiter.reset()