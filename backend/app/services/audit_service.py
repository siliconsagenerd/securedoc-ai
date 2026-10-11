import logging

from app.services.guard_service import GuardResult

logger = logging.getLogger(__name__)


class AuditService:
    def record(self, original: str, tokenized: str, guard: GuardResult) -> None:
        logger.info(
            "process chars=%d blocked=%s reason=%s",
            len(original),
            guard.blocked,
            guard.reason,
        )


audit_service = AuditService()
