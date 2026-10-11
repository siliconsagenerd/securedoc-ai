"""Append-only JSONL security audit log.

Only non-sensitive metadata is recorded. Raw document text, raw or decrypted
PII, token mappings, and API keys must never reach this logger.
"""

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings

_LOCK = threading.Lock()

_ALLOWED_FIELDS = {
    "event_id",
    "timestamp",
    "action",
    "status",
    "risk_level",
    "pii_found",
    "entity_types",
    "model",
    "latency_ms",
    "outcome",
    "client",
}


class AuditService:
    def __init__(self, log_path: Path | None = None) -> None:
        self._path = log_path or settings.audit_path

    def log(
        self,
        *,
        action: str,
        status: str,
        risk_level: str = "low",
        pii_found: bool = False,
        entity_types: list[str] | None = None,
        model: str = "",
        latency_ms: int = 0,
        outcome: str = "",
        client: str = "",
    ) -> str:
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "status": status,
            "risk_level": risk_level,
            "pii_found": pii_found,
            "entity_types": entity_types or [],
            "model": model,
            "latency_ms": latency_ms,
            "outcome": outcome,
            "client": client,
        }
        self._append(event)
        return event["event_id"]

    def _append(self, event: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({k: event[k] for k in _ALLOWED_FIELDS})
        with _LOCK, self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


audit_service = AuditService()
