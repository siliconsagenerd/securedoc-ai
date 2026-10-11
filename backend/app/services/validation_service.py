"""Client for the Java document-validation microservice.

Validation decides whether a document *may* be processed based on metadata only
(filename, declared content type, size) — no content is sent. The service is
called before any uploaded file is read into the pipeline.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field


class DocumentValidationError(Exception):
    """Raised when the validation service is unreachable or returns bad data.

    Callers must fail closed: reject the upload with a clear error rather than
    processing an unvalidated document.
    """


class ValidationResult(BaseModel):
    valid: bool
    reason: str | None = None
    checks: dict[str, bool] = Field(default_factory=dict)


class ValidationService:
    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def validate(self, *, filename: str, content_type: str, size_bytes: int) -> ValidationResult:
        try:
            response = httpx.post(
                f"{self._base_url}/api/v1/validate",
                json={
                    "filename": filename,
                    "content_type": content_type,
                    "size_bytes": size_bytes,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DocumentValidationError(
                "document validation service is unavailable"
            ) from exc
        return ValidationResult(**response.json())
