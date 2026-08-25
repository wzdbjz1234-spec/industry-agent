"""Transactional Outbox publisher application service."""

from __future__ import annotations

from datetime import UTC, datetime

from quality_case_agent.application.ports.event_bus import EventBus, EventEnvelope, OutboxStore


class OutboxPublisher:
    def __init__(self, outbox: OutboxStore, bus: EventBus, *, stream: str = "quality-events") -> None:
        self.outbox = outbox
        self.bus = bus
        self.stream = stream

    def run_once(self, *, limit: int = 100) -> int:
        published = 0
        for record in self.outbox.list_unpublished(limit):
            event_id = str(record["event_id"])
            event_type = str(record["event_type"])
            occurred_at = record["occurred_at"]
            if not isinstance(occurred_at, datetime):
                occurred_at = datetime.fromisoformat(str(occurred_at))
            payload = record["payload"]
            if not isinstance(payload, dict):
                raise TypeError(f"outbox payload must be an object: {event_id}")
            envelope = EventEnvelope(
                event_id=event_id,
                event_type=event_type,
                occurred_at=occurred_at,
                payload=dict(payload),
                stream=self.stream,
            )
            self.bus.publish(envelope)
            self.outbox.mark_published(event_id, datetime.now(UTC))
            published += 1
        return published
