"""Test configuration: set required env before the app imports settings."""

import os

os.environ.setdefault("TOKEN_VAULT_KEY", "test-vault-key-do-not-use")
os.environ.setdefault("SECUREDOC_API_KEY", "test-api-key-do-not-use")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("AUDIT_LOG_PATH", "./data/test_audit.log")
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test_securedoc.db")
# Keep the API-level suites below the rate limit; the limit itself is tested in
# test_rate_limit.py by lowering rate_limiter.limit directly.
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "1000")
