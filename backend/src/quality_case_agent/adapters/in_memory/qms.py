"""In-memory persistence for QMS consumer delivery state."""

from collections.abc import Sequence

from quality_case_agent.application.ports.qms import QmsDeliveryRecord


class InMemoryQmsDeliveryStore:
    """Model a database-backed consumer inbox with event/group idempotency."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], QmsDeliveryRecord] = {}

    def get(self, event_id: str, consumer_group: str) -> QmsDeliveryRecord | None:
        return self._records.get((consumer_group, event_id))

    def save(self, record: QmsDeliveryRecord) -> None:
        self._records[(record.consumer_group, record.event.event_id)] = record

    def _list(
        self, consumer_group: str, state: str
    ) -> Sequence[QmsDeliveryRecord]:
        return tuple(
            sorted(
                (
                    record
                    for record in self._records.values()
                    if record.consumer_group == consumer_group and record.state == state
                ),
                key=lambda record: record.event.occurred_at,
            )
        )

    def list_pending(self, consumer_group: str) -> Sequence[QmsDeliveryRecord]:
        return self._list(consumer_group, "PENDING")

    def list_dlq(self, consumer_group: str) -> Sequence[QmsDeliveryRecord]:
        return self._list(consumer_group, "DLQ")

    def list_processed(self, consumer_group: str) -> Sequence[QmsDeliveryRecord]:
        return self._list(consumer_group, "PROCESSED")
