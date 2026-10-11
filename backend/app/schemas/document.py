"""Pydantic schemas for the document-processing API."""

from typing import Literal

from pydantic import BaseModel, Field

Task = Literal["summarize", "extract_fields", "classify_document"]


class DocumentRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Document text to process")
    task: Task = Field(default="summarize", description="Processing task")


class GuardResult(BaseModel):
    allowed: bool
    risk_level: Literal["low", "medium", "high"]
    reasons: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    score: int = Field(default=0, ge=0, le=100)


class EntityMetadata(BaseModel):
    """Metadata about a redacted entity — never the raw value."""

    entity_type: str
    placeholder: str
    start: int
    end: int


class PIIResult(BaseModel):
    entity_count: int
    entity_types: list[str] = Field(default_factory=list)
    entities: list[EntityMetadata] = Field(default_factory=list)


class AuditEvent(BaseModel):
    event_id: str
    timestamp: str
    action: str
    status: str
    risk_level: str
    pii_found: bool
    entity_types: list[str] = Field(default_factory=list)
    model: str = ""
    latency_ms: int = 0
    outcome: str = ""


class DocumentResponse(BaseModel):
    task: Task
    filename: str = ""
    sanitized_preview: str
    pii: PIIResult
    llm_output: str
    audit_event_id: str
    latency_ms: int


class BlockedResponse(BaseModel):
    """Returned with HTTP 400 when the guard blocks a request."""

    message: str = "Request blocked by security policy"
    reasons: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    risk_level: str = "high"
    score: int = 0
    audit_event_id: str
