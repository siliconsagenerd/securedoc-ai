"""Test configuration: set required env before the app imports settings."""

import os

os.environ.setdefault("TOKEN_VAULT_KEY", "test-vault-key-do-not-use")
os.environ.setdefault("SECUREDOC_API_KEY", "test-api-key-do-not-use")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("AUDIT_LOG_PATH", "./data/test_audit.log")
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test_securedoc.db")
