import structlog

from .models import AuditEvent


class LiveAuditLogger:
    def __init__(self, repository):
        self.repository = repository

    async def record(self, event: AuditEvent) -> None:
        await self.repository.append_audit(event)
        structlog.get_logger().info(
            "LIVE_AUDIT",
            event_type=event.event_type,
            execution_request_id=str(event.execution_request_id) if event.execution_request_id else None,
            symbol=event.symbol,
            result=event.result,
        )
