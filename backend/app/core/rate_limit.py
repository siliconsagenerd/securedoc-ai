"""In-memory fixed-window rate limiting keyed by client IP.

Abuse protection for the document endpoints. A single shared API key makes
per-key limits meaningless, so the identity is the client IP (honoring
``X-Real-IP``/``X-Forwarded-For`` set by nginx). Restarting the process resets
all windows; production with many instances should move this to a shared store.
"""

import hashlib
import threading
import time

from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.services.audit_service import audit_service


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def check(self, identity: str) -> tuple[bool, int]:
        """Return ``(allowed, retry_after_seconds)`` for a new hit."""
        now = time.monotonic()
        with self._lock:
            if len(self._hits) > 10_000:
                self._prune(now)
            start, count = self._hits.get(identity, (now, 0))
            if now - start >= self.window_seconds:
                start, count = now, 0
            count += 1
            self._hits[identity] = (start, count)
            if count > self.limit:
                retry_after = int(self.window_seconds - (now - start)) + 1
                return False, retry_after
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def _prune(self, now: float) -> None:
        expired = [
            identity
            for identity, (start, _) in self._hits.items()
            if now - start >= self.window_seconds
        ]
        for identity in expired:
            del self._hits[identity]


def _client_ip(request: Request) -> str:
    # Identity must come from a header the client cannot set. Our nginx always
    # overwrites X-Real-IP with $remote_addr, so trust it first. X-Forwarded-For
    # is client-appendable, so only its right-most (proxy-added) entry is used —
    # never the left-most, which the caller controls and could rotate to defeat
    # the limit. Between the two, a spoofed XFF cannot mint new buckets.
    real = request.headers.get("x-real-ip")
    if real:
        return real.split(",")[-1].strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _identity_hash(identity: str) -> str:
    return hashlib.sha256(identity.encode()).hexdigest()[:12]


def client_identity(request: Request) -> str:
    return _client_ip(request)


def enforce_rate_limit(request: Request) -> None:
    """FastAPI dependency: reject bursts past the per-minute limit with 429."""
    identity = client_identity(request)
    allowed, retry_after = rate_limiter.check(identity)
    if not allowed:
        audit_service.log(
            action="rate_limit",
            status="blocked",
            outcome="rate_limited",
            client=_identity_hash(identity),
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )


rate_limiter = RateLimiter(settings.rate_limit_per_minute)