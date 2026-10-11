"""HTTP API routes."""

import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app import __version__
from app.core.config import settings
from app.schemas.document import (
    BlockedResponse,
    DocumentRequest,
    DocumentResponse,
    EntityMetadata,
    PIIResult,
)
from app.services.audit_service import audit_service
from app.services.guard_service import guard_service
from app.services.llm_service import LLMError, llm_service
from app.services.pii_service import get_pii_service

router = APIRouter(prefix="/api")

_PREVIEW_CHARS = 500


@router.get("/version", tags=["meta"])
async def version() -> dict[str, str]:
    return {"name": "SecureDoc AI", "version": __version__}


@router.post(
    "/process-document",
    response_model=DocumentResponse,
    responses={400: {"model": BlockedResponse}},
    tags=["documents"],
)
async def process_document(request: DocumentRequest):
    started = time.perf_counter()

    if len(request.text.encode("utf-8")) > settings.max_upload_bytes:
        return JSONResponse(
            status_code=413,
            content={"message": "Document exceeds the maximum allowed size"},
        )

    # 1. Prompt-injection / jailbreak guard.
    verdict = guard_service.inspect(request.text)

    if not verdict.allowed:
        event_id = audit_service.log(
            action="guard_block",
            status="blocked",
            risk_level=verdict.risk_level,
            pii_found=False,
            entity_types=[],
            model="",
            latency_ms=_elapsed_ms(started),
            outcome="blocked",
        )
        return JSONResponse(
            status_code=400,
            content=BlockedResponse(
                reasons=verdict.reasons,
                risk_level=verdict.risk_level,
                audit_event_id=event_id,
            ).model_dump(),
        )

    # 2. PII redaction. Only the sanitized text proceeds.
    redaction = get_pii_service().redact(request.text)
    entity_types = sorted({e.entity_type for e in redaction.entities})

    # 3. LLM call on sanitized text only. The vault never leaves the backend.
    model = llm_service.model
    try:
        llm_output = llm_service.run(request.task, redaction.sanitized_text)
        outcome = "success"
    except LLMError:
        llm_output = (
            "LLM provider is not configured. Sanitized text was produced and "
            "PII was redacted locally; no data was sent externally."
        )
        outcome = "llm_unavailable"

    latency_ms = _elapsed_ms(started)

    # 4. Audit event (metadata only).
    event_id = audit_service.log(
        action="process_document",
        status="allowed",
        risk_level=verdict.risk_level,
        pii_found=redaction.entity_count > 0,
        entity_types=entity_types,
        model=model,
        latency_ms=latency_ms,
        outcome=outcome,
    )

    return DocumentResponse(
        task=request.task,
        sanitized_preview=redaction.sanitized_text[:_PREVIEW_CHARS],
        pii=PIIResult(
            entity_count=redaction.entity_count,
            entity_types=entity_types,
            entities=[
                EntityMetadata(
                    entity_type=e.entity_type,
                    placeholder=e.placeholder,
                    start=e.start,
                    end=e.end,
                )
                for e in redaction.entities
            ],
        ),
        llm_output=llm_output,
        audit_event_id=event_id,
        latency_ms=latency_ms,
    )


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
