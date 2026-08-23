"""Consumer worker for approved investigation events sent to QMS."""

from collections.abc import Sequence
from datetime import UTC, datetime
from time import perf_counter
from typing import Literal

from quality_case_agent.application.observability.service import (
    RetryAuditRecord,
    WorkerMetricsRegistry,
    redact_error,
)
from quality_case_agent.application.ports.qms import (
    QmsDeliveryRecord,
    QmsDeliveryStore,
    QmsPermanentError,
    QmsTransientError,
)
from quality_case_agent.application.qms.service import QmsIntegrationService
from quality_case_agent.contracts.approval import ApprovalEventContract
from quality_case_agent.contracts.qms import QmsTaskCreatedEventContract


class QmsIntegrationWorker:
    """Apply approved events once, retry transient QMS failures, and retain DLQ state."""

    def __init__(
        self,
        service: QmsIntegrationService,
        delivery_store: QmsDeliveryStore,
        *,
        consumer_group: str = "qms-integration-worker",
        max_attempts: int = 3,
        metrics: WorkerMetricsRegistry | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self._service = service
        self._delivery_store = delivery_store
        self._consumer_group = consumer_group
        self._max_attempts = max_attempts
        self._metrics = metrics
        self._retry_audit: list[RetryAuditRecord] = []

    def handle(self, event: ApprovalEventContract) -> QmsTaskCreatedEventContract | None:
        started = perf_counter()
        existing = self._delivery_store.get(event.event_id, self._consumer_group)
        if existing is not None:
            if existing.state == "PROCESSED":
                return existing.result
            if existing.state == "DLQ":
                return None
            attempts = existing.attempts + 1
        else:
            attempts = 1

        try:
            result = self._service.handle_approved(event)
        except (QmsTransientError, TimeoutError, ConnectionError) as exc:
            state: Literal["PENDING", "DLQ"] = (
                "PENDING" if attempts < self._max_attempts else "DLQ"
            )
            self._save(event, attempts, state, str(exc), error_type=type(exc).__name__)
            self._observe(
                event,
                state,
                started,
                type(exc).__name__,
                str(exc),
                error_category="SYSTEM_FAILURE",
            )
            return None
        except (QmsPermanentError, KeyError, ValueError) as exc:
            self._save(event, attempts, "DLQ", str(exc), error_type=type(exc).__name__)
            self._observe(
                event,
                "DLQ",
                started,
                type(exc).__name__,
                str(exc),
                error_category="BUSINESS_REJECTION",
            )
            return None

        self._save(event, attempts, "PROCESSED", result=result)
        self._observe(event, "PROCESSED", started)
        return result

    def retry_pending(self, operator_id: str = "system") -> tuple[QmsTaskCreatedEventContract, ...]:
        results: list[QmsTaskCreatedEventContract] = []
        for record in self._delivery_store.list_pending(self._consumer_group):
            previous_state = record.state
            result = self.handle(record.event)
            updated = self._delivery_store.get(record.event.event_id, self._consumer_group)
            if updated is not None:
                self._audit(record.event.event_id, operator_id, previous_state, updated)
            if result is not None:
                results.append(result)
        return tuple(results)

    def retry_dlq(
        self, event_id: str, *, operator_id: str
    ) -> QmsTaskCreatedEventContract | None:
        record = self._delivery_store.get(event_id, self._consumer_group)
        if record is None:
            raise KeyError(f"delivery event not found: {event_id}")
        if record.state != "DLQ":
            raise ValueError("only DLQ deliveries may be explicitly retried")
        previous_state = record.state
        record.state = "PENDING"
        record.attempts = 0
        record.updated_at = datetime.now(UTC)
        self._delivery_store.save(record)
        result = self.handle(record.event)
        updated = self._delivery_store.get(event_id, self._consumer_group)
        if updated is not None:
            self._audit(event_id, operator_id, previous_state, updated)
        return result

    def retry_audit(self) -> tuple[RetryAuditRecord, ...]:
        return tuple(self._retry_audit)

    def pending(self) -> Sequence[QmsDeliveryRecord]:
        return self._delivery_store.list_pending(self._consumer_group)

    def dlq(self) -> Sequence[QmsDeliveryRecord]:
        return self._delivery_store.list_dlq(self._consumer_group)

    def processed(self) -> Sequence[QmsDeliveryRecord]:
        return self._delivery_store.list_processed(self._consumer_group)

    def _save(
        self,
        event: ApprovalEventContract,
        attempts: int,
        state: Literal["PENDING", "PROCESSED", "DLQ"],
        last_error: str | None = None,
        result: QmsTaskCreatedEventContract | None = None,
        error_type: str | None = None,
    ) -> None:
        existing = self._delivery_store.get(event.event_id, self._consumer_group)
        now = datetime.now(UTC)
        self._delivery_store.save(
            QmsDeliveryRecord(
                event=event,
                consumer_group=self._consumer_group,
                attempts=attempts,
                state=state,
                last_error=redact_error(last_error) if last_error else None,
                result=result,
                created_at=existing.created_at if existing is not None else now,
                updated_at=now,
                last_error_type=error_type,
                last_error_at=now if last_error else None,
            )
        )

    def _observe(
        self,
        event: ApprovalEventContract,
        state: str,
        started: float,
        error_type: str | None = None,
        error: str | None = None,
        error_category: str | None = None,
    ) -> None:
        if self._metrics is not None:
            self._metrics.observe(
                self._consumer_group,
                status=state,
                duration_ms=int((perf_counter() - started) * 1000),
                event_id=event.event_id,
                error_type=error_type,
                error=error,
                error_category=error_category,
            )

    def _audit(
        self,
        event_id: str,
        operator_id: str,
        previous_state: str,
        record: QmsDeliveryRecord,
    ) -> None:
        self._retry_audit.append(
            RetryAuditRecord(
                event_id=event_id,
                consumer_group=self._consumer_group,
                operator_id=operator_id,
                requested_at=datetime.now(UTC),
                previous_state=previous_state,
                resulting_state=record.state,
                attempts=record.attempts,
            )
        )
