"""LLM integration.

Supports two backends:
- Google Gemini via the google-genai SDK (default when no base URL is set).
- Any OpenAI-compatible endpoint (e.g. OmniRoute) when ``llm_base_url`` is set
  or the configured API key looks like an OmniRoute key (``sk-...``). Configured
  model names in ``llm_fallback_models`` (comma-separated) are tried in order
  after the primary; OmniRoute mode falls back to Laya / Laya v2 by default.
"""

from __future__ import annotations

import logging
from typing import List

import httpx
from google import genai
from google.genai import types as genai_types

from app.core.config import settings

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_MS = 20_000

_TASK_PROMPTS: dict[str, str] = {
    "summarize": (
        "You are a document assistant. Summarize the following document "
        "concisely in 2-4 sentences. Do not include any personal data."
    ),
    "extract_fields": (
        "You are a document assistant. Extract the key fields from the "
        "following document as a JSON object. Do not include personal data."
    ),
    "classify_document": (
        "You are a document assistant. Classify the document type and "
        "topic in one sentence."
    ),
}

_DEFAULT_OMNIROUTE_FALLBACKS = ["laya/laya", "laya-v2/laya-v2"]


class LLMError(Exception):
    """Raised when the LLM provider is unavailable or fails."""


class LLMService:
    def __init__(self) -> None:
        self._client = None

    @property
    def _api_key(self) -> str:
        return settings.llm_api_key or settings.gemini_api_key

    @property
    def _base_url(self) -> str:
        url = settings.llm_base_url
        if not url and self._api_key.startswith("sk-"):
            url = "http://127.0.0.1:20128/v1"
        return url.rstrip("/") if url else ""

    @property
    def _omniroute_mode(self) -> bool:
        return bool(self._base_url)

    @property
    def available(self) -> bool:
        if self._omniroute_mode:
            return bool(self._api_key and self._base_url)
        return bool(settings.gemini_api_key)

    @property
    def model(self) -> str:
        return settings.llm_model or settings.gemini_model

    @property
    def _models_to_try(self) -> List[str]:
        models = [self.model]
        raw = settings.llm_fallback_models
        if raw:
            for m in raw.split(","):
                m = m.strip()
                if m and m not in models:
                    models.append(m)
        elif self._omniroute_mode:
            for m in _DEFAULT_OMNIROUTE_FALLBACKS:
                if m not in models:
                    models.append(m)
        return models

    def _get_client(self):
        if self._client is None:
            self._client = genai.Client(
                api_key=settings.gemini_api_key,
                http_options=genai_types.HttpOptions(
                    timeout=_REQUEST_TIMEOUT_MS,
                    retry_options=genai_types.HttpRetryOptions(attempts=1),
                ),
            )
        return self._client

    def run(self, task: str, sanitized_text: str) -> str:
        if not self.available:
            raise LLMError("no API key configured")
        prompt = _TASK_PROMPTS.get(task, _TASK_PROMPTS["summarize"])
        full_prompt = f"{prompt}\n\nDocument:\n{sanitized_text}"

        if self._omniroute_mode:
            return self._run_omniroute(full_prompt)
        return self._run_gemini(full_prompt)

    def _run_gemini(self, full_prompt: str) -> str:
        client = self._get_client()
        seen = set()
        unique = []
        for m in [self.model, settings.gemini_model, "gemini-2.0-flash"]:
            if m and m not in seen:
                seen.add(m)
                unique.append(m)
        for model_name in unique:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                )
                if response.text:
                    return response.text
            except Exception as exc:  # noqa: BLE001
                logger.warning("Gemini model %s failed: %s", model_name, exc)
                continue
        raise LLMError("all Gemini models failed")

    def _run_omniroute(self, full_prompt: str) -> str:
        url = f"{self._base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        last_exc = None
        for model_name in self._models_to_try:
            try:
                resp = httpx.post(
                    url,
                    headers=headers,
                    json={
                        "model": model_name,
                        "messages": [{"role": "user", "content": full_prompt}],
                        "reasoning_effort": "none",
                    },
                    timeout=20.0,
                )
                if resp.status_code != 200:
                    logger.warning("OmniRoute model %s returned %s: %s", model_name, resp.status_code, resp.text[:200])
                    continue
                data = resp.json()
                choices = data.get("choices") or []
                msg = (choices[0].get("message") or {}) if choices else {}
                content = msg.get("content")
                if content:
                    return content
            except Exception as exc:  # noqa: BLE001
                logger.warning("OmniRoute model %s failed: %s", model_name, exc)
                last_exc = exc
                continue
        raise LLMError(f"all OmniRoute models failed: {last_exc}")


llm_service = LLMService()