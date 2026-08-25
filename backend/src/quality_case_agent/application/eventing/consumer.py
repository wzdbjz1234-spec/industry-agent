"""Provider-neutral reliable consumer with Inbox and bounded retry semantics."""

from __future__ import annotations

from datetime import UTC, datetime

from quality_case_agent.application.ports.event_bus import (
    ConsumeResult,
    EventBus,
    EventHandler,
    InboxStore,
)


class TransientEventError(RuntimeError):
    """Handler may raise this when retrying can succeed later."""


class PermanentEventError(RuntimeError):
    """Handler may raise this when the event must go to a DLQ."""


class ReliableEventConsumer:
    """Owns schema boundary, Inbox check, ACK, retry and DLQ behavior.

    Worker-specific modules only provide a handler.  This is intentionally a deep
    seam so Redis and test adapters share exactly the same side-effect rules.
    """

    def __init__(
        self,
        bus: EventBus,
        inbox: InboxStore,
        *,
        consumer_group: str,
        consumer_name: str,
        max_attempts: int = 5,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.bus = bus
        self.inbox = inbox
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self.max_attempts = max_attempts

    def run_once(self, handler: EventHandler, *, limit: int = 10) -> ConsumeResult:
        deliveries = self.bus.read(self.consumer_group, self.consumer_name, limit=limit)
        result = ConsumeResult(read=len(deliveries))
        errors: list[str] = []
        for delivery in deliveries:
            event_id = delivery.envelope.event_id
            if self.inbox.seen(self.consumer_group, event_id):
                self.bus.ack(delivery)
                result = _plus(result, skipped_duplicate=1)
                continue
            try:
                handler(delivery.envelope)
            except Exception as exc:  # noqa: BLE001 - classify once at the boundary
                message = _safe_error(exc)
                errors.append(message)
                is_dlq = self.bus.retry(
                    delivery,
                    error=message,
                    max_attempts=delivery.attempts if isinstance(exc, PermanentEventError) else self.max_attempts,
                )
                if is_dlq:
                    result = _plus(result, dead_lettered=1, failed=1)
                else:
                    result = _plus(result, retried=1, failed=1)
                continue
            self.inbox.mark(self.consumer_group, event_id, datetime.now(UTC))
            self.bus.ack(delivery)
            result = _plus(result, processed=1)
        return _replace_errors(result, tuple(errors))


def _plus(result: ConsumeResult, **changes: int) -> ConsumeResult:
    return ConsumeResult(
        read=result.read + changes.get("read", 0),
        processed=result.processed + changes.get("processed", 0),
        skipped_duplicate=result.skipped_duplicate + changes.get("skipped_duplicate", 0),
        retried=result.retried + changes.get("retried", 0),
        dead_lettered=result.dead_lettered + changes.get("dead_lettered", 0),
        failed=result.failed + changes.get("failed", 0),
        errors=result.errors,
    )


def _replace_errors(result: ConsumeResult, errors: tuple[str, ...]) -> ConsumeResult:
    return ConsumeResult(
        read=result.read,
        processed=result.processed,
        skipped_duplicate=result.skipped_duplicate,
        retried=result.retried,
        dead_lettered=result.dead_lettered,
        failed=result.failed,
        errors=errors,
    )


def _safe_error(exc: Exception) -> str:
    value = " ".join(str(exc).split())[:512]
    return value or type(exc).__name__
