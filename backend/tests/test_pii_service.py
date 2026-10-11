import re

from app.services.pii_service import get_pii_service

PLACEHOLDER_RE = re.compile(r"^\[PII_[A-Z_]+_[0-9a-f]{10}\]$")


def test_email_is_removed_from_sanitized_text():
    svc = get_pii_service()
    result = svc.redact("Reach me at jane.doe@example.com today.")
    assert "jane.doe@example.com" not in result.sanitized_text
    assert "EMAIL_ADDRESS" in {e.entity_type for e in result.entities}


def test_german_iban_is_detected():
    svc = get_pii_service()
    result = svc.redact("Transfer to DE89 3704 0044 0532 0130 00 please.")
    assert "IBAN_CODE" in {e.entity_type for e in result.entities}
    assert "DE89" not in result.sanitized_text


def test_person_is_detected():
    svc = get_pii_service()
    result = svc.redact("Alice Johnson approved the invoice.")
    assert "PERSON" in {e.entity_type for e in result.entities}


def test_placeholder_format_is_correct():
    svc = get_pii_service()
    result = svc.redact("Email jane.doe@example.com now.")
    placeholders = list(result.encrypted_mappings.keys())
    assert placeholders, "expected at least one placeholder"
    assert all(PLACEHOLDER_RE.match(p) for p in placeholders)


def test_rehydration_restores_original_text():
    svc = get_pii_service()
    original = "Alice Johnson (jane.doe@example.com) IBAN DE89 3704 0044 0532 0130 00."
    result = svc.redact(original)
    restored = svc.rehydrate(result.sanitized_text, result.encrypted_mappings)
    assert restored == original
