"""Guardrails on the Gemini client: bounded timeout, single attempt.

Regression guard for the production bug where the SDK's default retry loop
turned a fast provider 5xx/429 into a multi-minute hang, which nginx surfaced
as a 504 Gateway Time-out to the browser.
"""

from app.core.config import settings
from app.services.llm_service import _REQUEST_TIMEOUT_MS, LLMService


def test_client_call_is_bounded(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "dummy-key")

    http_options = LLMService()._get_client()._api_client._http_options

    assert http_options.timeout == _REQUEST_TIMEOUT_MS
    assert http_options.retry_options.attempts == 1
