"""HTTP API routes."""

import time

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app import __version__
from app.core.auth import require_api_key
from app.core.config import settings
from app.schemas.document import (
    BlockedResponse,
    DocumentRequest,
    DocumentResponse,
    EntityMetadata,
    PIIResult,
    Task,
)
from app.services.audit_service import audit_service
from app.services.extraction_service import ExtractionError, extract_text
from app.services.guard_service import guard_service
from app.services.llm_service import LLMError, llm_service
from app.services.pii_service import get_pii_service
from app.services.validation_service import (
    DocumentValidationError,
    ValidationService,
)

router = APIRouter(prefix="/api")

_PREVIEW_CHARS = 500

validation_service = ValidationService(settings.java_validator_url)


@router.get("/version", tags=["meta"])
async def version() -> dict[str, str]:
    return {"name": "SecureDoc AI", "version": __version__}


@router.post(
    "/process-document",
    response_model=DocumentResponse,
    responses={400: {"model": BlockedResponse}, 401: {"description": "Missing or invalid API key"}},
    tags=["documents"],
    dependencies=[Depends(require_api_key)],
)
async def process_document(request: DocumentRequest):
    if len(request.text.encode("utf-8")) > settings.max_upload_bytes:
        return _too_large()
    return _run_pipeline(request.text, request.task)


@router.post(
    "/upload-document",
    response_model=DocumentResponse,
    responses={
        400: {"description": "Rejected by the document validator or the injection guard"},
        401: {"description": "Missing or invalid API key"},
        413: {"description": "File exceeds the maximum allowed size"},
        415: {"description": "Unsupported or unreadable document"},
        503: {"description": "Document validation service unavailable"},
    },
    tags=["documents"],
    dependencies=[Depends(require_api_key)],
)
async def upload_document(
    file: UploadFile = File(...),
    task: Task = Form("summarize"),
):
    filename = file.filename or ""
    content_type = file.content_type or ""
    content = await file.read()

    if len(content) > settings.max_upload_bytes:
        return _too_large()

    try:
        validation = validation_service.validate(
            filename=filename, content_type=content_type, size_bytes=len(content)
        )
    except DocumentValidationError:
        return JSONResponse(
            status_code=503,
            content={"message": "Document validation service is unavailable; upload not processed"},
        )
    if not validation.valid:
        return JSONResponse(
            status_code=400,
            content={"message": f"File rejected: {validation.reason}", "checks": validation.checks},
        )

    try:
        text = extract_text(filename, content)  # in-memory only; never persisted
    except ExtractionError as exc:
        return JSONResponse(status_code=415, content={"message": str(exc)})

    return _run_pipeline(text, task, filename=filename)


def _run_pipeline(text: str, task: Task, filename: str = ""):
    """Guard -> redact -> LLM -> audit. Shared by the text and upload endpoints."""
    started = time.perf_counter()

    # 1. Prompt-injection / jailbreak guard.
    verdict = guard_service.inspect(text)
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
                categories=verdict.categories,
                risk_level=verdict.risk_level,
                score=verdict.score,
                audit_event_id=event_id,
            ).model_dump(),
        )

    # 2. PII redaction. Only the sanitized text proceeds.
    redaction = get_pii_service().redact(text)
    entity_types = sorted({e.entity_type for e in redaction.entities})

    # 3. LLM call on sanitized text only. The vault never leaves the backend.
    model = llm_service.model
    try:
        llm_output = llm_service.run(task, redaction.sanitized_text)
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
        task=task,
        filename=filename,
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


def _too_large() -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content={"message": "Document exceeds the maximum allowed size"},
    )


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
