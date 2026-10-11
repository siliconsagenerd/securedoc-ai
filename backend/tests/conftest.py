"""Test configuration: set required env before the app imports settings."""

import os

import pytest

# SECUREDOC_API_KEY must be in place before app.core.config.Settings is
# instantiated (settings reads env at import time). setdefault() keeps any key
# a developer exported explicitly, so auth tests always exercise the key the
# app actually validates against.
os.environ.setdefault("TOKEN_VAULT_KEY", "test-vault-key-do-not-use")
os.environ.setdefault("SECUREDOC_API_KEY", "test-api-key")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("AUDIT_LOG_PATH", "./data/test_audit.log")
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test_securedoc.db")
# Keep the API-level suites below the rate limit; the limit itself is tested in
# test_rate_limit.py by lowering rate_limiter.limit directly.
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "1000")


@pytest.fixture
def test_api_key() -> str:
    """The API key the running app was configured with."""
    return os.environ["SECUREDOC_API_KEY"]


@pytest.fixture
def auth_headers(test_api_key: str) -> dict[str, str]:
    """Headers that authenticate every protected request."""
    return {"X-API-Key": test_api_key}
