"""Encryption helpers for the local PII token vault.

The vault maps ephemeral placeholders (e.g. ``[PII_EMAIL_ADDRESS_ab12cd34ef]``)
back to the original sensitive value. It never leaves the backend and is
encrypted at rest with Fernet (AES-128-CBC + HMAC).
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def derive_fernet_key(secret: str) -> bytes:
    """Return a valid Fernet key derived from ``secret``.

    Accepts either a ready-made Fernet key (44-char urlsafe base64) or an
    arbitrary passphrase, which is hashed to a 32-byte key.
    """
    if not secret:
        raise ValueError(
            "TOKEN_VAULT_KEY is not set; cannot create the PII token vault key"
        )
    candidate = secret.encode()
    try:
        Fernet(candidate)
        return candidate
    except (ValueError, TypeError):
        digest = hashlib.sha256(candidate).digest()
        return base64.urlsafe_b64encode(digest)


def _fernet() -> Fernet:
    return Fernet(derive_fernet_key(settings.token_vault_key))


def encrypt_string(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_string(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt value with the configured vault key") from exc
