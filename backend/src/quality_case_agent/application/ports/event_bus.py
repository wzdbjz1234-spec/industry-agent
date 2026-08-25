"""Deep event-stream port shared by Outbox publishers and Worker handlers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    event_id: str
    event_type: str
    occurred_at: datetime
    payload: dict[str, object]
    stream: str = "quality-events"

    def __post_init__(self) -> None:
        if not self.event_id or not self.event_type:
            raise ValueError("event_id and event_type are required")
        if self.occurred_at.tzinfo is None:
            object.__setattr__(self, "occurred_at", self.occurred_at.replace(tzinfo=UTC))


@dataclass(frozen=True, slots=True)
class EventDelivery:
    delivery_id: str
    envelope: EventEnvelope
    consumer_group: str
    consumer_name: str
    delivered_at: datetime
    attempts: int = 1


@dataclass(frozen=True, slots=True)
class ConsumeResult:
    read: int = 0
    processed: int = 0
    skipped_duplicate: int = 0
    retried: int = 0
    dead_lettered: int = 0
    failed: int = 0
    errors: tuple[str, ...] = field(default_factory=tuple)


class EventBus(Protocol):
    def publish(self, envelope: EventEnvelope) -> str:
        """Append an envelope and return the provider stream ID."""

    def read(self, consumer_group: str, consumer_name: str, *, limit: int = 10) -> Sequence[EventDelivery]:
        """Read new or visibility-timeout pending deliveries."""

    def ack(self, delivery: EventDelivery) -> None:
        """Acknowledge a provider delivery."""

    def retry(self, delivery: EventDelivery, *, error: str, max_attempts: int) -> bool:
        """Return True when the delivery was moved to a DLQ."""

    def pending_count(self, consumer_group: str) -> int:
        """Return the number of unacknowledged deliveries."""

    def oldest_pending_age_seconds(self, consumer_group: str) -> float:
        """Return age of oldest pending delivery, or zero when empty."""


class InboxStore(Protocol):
    def seen(self, consumer_group: str, event_id: str) -> bool:
        """Check whether the business side effect already committed."""

    def mark(self, consumer_group: str, event_id: str, processed_at: datetime) -> None:
        """Record the idempotency key after the handler succeeds."""


class EventHandler(Protocol):
    def __call__(self, envelope: EventEnvelope) -> None: ...


class OutboxStore(Protocol):
    def list_unpublished(self, limit: int = 100) -> Sequence[dict[str, object]]: ...

    def mark_published(self, event_id: str, published_at: datetime) -> None: ...

