"""Deterministic EventBus and Inbox adapters for tests and local development."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from quality_case_agent.application.ports.event_bus import (
    EventBus,
    EventDelivery,
    EventEnvelope,
    InboxStore,
)


@dataclass(slots=True)
class _Pending:
    delivery: EventDelivery
    next_visible_at: datetime
    last_error: str | None = None


class InMemoryEventBus(EventBus):
    def __init__(self, *, visibility_timeout_seconds: float = 0.0, retry_backoff_seconds: float = 0.0) -> None:
        self.visibility_timeout = timedelta(seconds=max(0.0, visibility_timeout_seconds))
        self.retry_backoff = max(0.0, retry_backoff_seconds)
        self._streams: dict[str, list[EventEnvelope]] = defaultdict(list)
        self._acked: set[tuple[str, str]] = set()
        self._pending: dict[tuple[str, str], _Pending] = {}
        self._dead_letters: list[tuple[EventDelivery, str]] = []
        self._sequence = 0

    def publish(self, envelope: EventEnvelope) -> str:
        self._sequence += 1
        self._streams[envelope.stream].append(envelope)
        return f"{self._sequence}-0"

    def read(self, consumer_group: str, consumer_name: str, *, limit: int = 10) -> tuple[EventDelivery, ...]:
        now = datetime.now(UTC)
        result: list[EventDelivery] = []
        for stream in tuple(self._streams.values()):
            for envelope in stream:
                key = (consumer_group, envelope.event_id)
                if key in self._acked or len(result) >= limit:
                    continue
                pending = self._pending.get(key)
                if pending is not None and pending.next_visible_at > now:
                    continue
                attempts = pending.delivery.attempts + 1 if pending else 1
                self._sequence += 1
                delivery = EventDelivery(
                    delivery_id=f"{self._sequence}-0",
                    envelope=envelope,
                    consumer_group=consumer_group,
                    consumer_name=consumer_name,
                    delivered_at=now,
                    attempts=attempts,
                )
                self._pending[key] = _Pending(delivery, now + self.visibility_timeout)
                result.append(delivery)
        return tuple(result)

    def ack(self, delivery: EventDelivery) -> None:
        key = (delivery.consumer_group, delivery.envelope.event_id)
        self._acked.add(key)
        self._pending.pop(key, None)

    def retry(self, delivery: EventDelivery, *, error: str, max_attempts: int) -> bool:
        key = (delivery.consumer_group, delivery.envelope.event_id)
        if delivery.attempts >= max_attempts:
            self._dead_letters.append((delivery, error))
            self._acked.add(key)
            self._pending.pop(key, None)
            return True
        pending = self._pending.get(key)
        if pending is not None:
            pending.next_visible_at = datetime.now(UTC) + timedelta(
                seconds=self.retry_backoff * (2 ** max(0, delivery.attempts - 1))
            )
            pending.last_error = error
        return False

    def pending_count(self, consumer_group: str) -> int:
        return sum(1 for group, _ in self._pending if group == consumer_group)

    def oldest_pending_age_seconds(self, consumer_group: str) -> float:
        now = datetime.now(UTC)
        values = [
            (now - item.delivery.delivered_at).total_seconds()
            for (group, _), item in self._pending.items()
            if group == consumer_group
        ]
        return max(values, default=0.0)

    @property
    def dead_letters(self) -> tuple[tuple[EventDelivery, str], ...]:
        return tuple(self._dead_letters)


class InMemoryInboxStore(InboxStore):
    def __init__(self) -> None:
        self._keys: set[tuple[str, str]] = set()

    def seen(self, consumer_group: str, event_id: str) -> bool:
        return (consumer_group, event_id) in self._keys

    def mark(self, consumer_group: str, event_id: str, processed_at: datetime) -> None:
        self._keys.add((consumer_group, event_id))


class InMemoryOutboxStore:
    def __init__(self) -> None:
        self._records: dict[str, dict[str, object]] = {}

    def append(self, event_id: str, event_type: str, payload: dict[str, object], *, occurred_at: datetime | None = None) -> None:
        self._records.setdefault(event_id, {
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": occurred_at or datetime.now(UTC),
            "payload": dict(payload),
            "published_at": None,
        })

    def list_unpublished(self, limit: int = 100) -> tuple[dict[str, object], ...]:
        return tuple(item for item in self._records.values() if item["published_at"] is None)[:limit]

    def mark_published(self, event_id: str, published_at: datetime) -> None:
        self._records[event_id]["published_at"] = published_at
