"""Tests for the Java validation-service client."""

import httpx
import pytest

from app.services import validation_service
from app.services.validation_service import DocumentValidationError, ValidationService


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error", request=httpx.Request("POST", "http://x"), response=self
            )

    def json(self) -> dict:
        return self._payload


def test_returns_parsed_result(monkeypatch):
    monkeypatch.setattr(
        validation_service.httpx,
        "post",
        lambda *a, **k: _FakeResponse(
            {"valid": True, "reason": None, "checks": {"file_extension": True}}
        ),
    )
    result = ValidationService("http://java:8080").validate(
        filename="a.pdf", content_type="application/pdf", size_bytes=10
    )
    assert result.valid is True
    assert result.checks["file_extension"] is True


def test_returns_rejection_with_reason(monkeypatch):
    monkeypatch.setattr(
        validation_service.httpx,
        "post",
        lambda *a, **k: _FakeResponse(
            {"valid": False, "reason": "unsupported", "checks": {"file_extension": False}}
        ),
    )
    result = ValidationService("http://java:8080").validate(
        filename="a.exe", content_type="application/octet-stream", size_bytes=10
    )
    assert result.valid is False
    assert result.reason == "unsupported"


def test_unreachable_service_fails_closed(monkeypatch):
    def _boom(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(validation_service.httpx, "post", _boom)
    with pytest.raises(DocumentValidationError):
        ValidationService("http://java:8080").validate(
            filename="a.pdf", content_type="application/pdf", size_bytes=10
        )


def test_error_status_fails_closed(monkeypatch):
    monkeypatch.setattr(
        validation_service.httpx, "post", lambda *a, **k: _FakeResponse({}, status_code=500)
    )
    with pytest.raises(DocumentValidationError):
        ValidationService("http://java:8080").validate(
            filename="a.pdf", content_type="application/pdf", size_bytes=10
        )
