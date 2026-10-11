"""API-key authentication for protected endpoints.

The expected key comes from the ``SECUREDOC_API_KEY`` environment variable.
Comparison is constant-time and the key value is never logged.
"""

import hmac
import logging

from fastapi import Header, HTTPException, status

from app.core.config import settings

logger = logging.getLogger("securedoc.auth")


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Dependency that rejects requests without a valid ``X-API-Key`` header."""
    expected = settings.securedoc_api_key

    if not expected:
        logger.error("SECUREDOC_API_KEY is not configured; rejecting protected request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is not configured on the server",
        )

    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        logger.warning("Rejected request with missing or invalid API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
        )
