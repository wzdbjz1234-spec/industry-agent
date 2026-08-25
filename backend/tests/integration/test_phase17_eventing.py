"""Phase 17 Outbox, Inbox, retry and DLQ semantics."""

from datetime import UTC, datetime

from quality_case_agent.adapters.redis_streams.in_memory import (
    InMemoryEventBus,
    InMemoryInboxStore,
    InMemoryOutboxStore,
)
from quality_case_agent.application.eventing.consumer import (
    PermanentEventError,
    ReliableEventConsumer,
)
from quality_case_agent.application.eventing.publisher import OutboxPublisher
from quality_case_agent.application.ports.event_bus import EventEnvelope


def test_outbox_publishes_only_unpublished_rows() -> None:
    outbox = InMemoryOutboxStore()
    bus = InMemoryEventBus()
    outbox.append("evt-1", "quality.case.opened.v1", {"case_id": "case-1"}, occurred_at=datetime.now(UTC))
    publisher = OutboxPublisher(outbox, bus)
    assert publisher.run_once() == 1
    assert publisher.run_once() == 0
    assert bus.read("case-detector", "worker-1")[0].envelope.event_id == "evt-1"


def test_inbox_prevents_duplicate_business_side_effect() -> None:
    bus = InMemoryEventBus()
    inbox = InMemoryInboxStore()
    bus.publish(EventEnvelope("evt-1", "quality.case.opened.v1", datetime.now(UTC), {"case_id": "case-1"}))
    consumer = ReliableEventConsumer(
        bus, inbox, consumer_group="investigation", consumer_name="worker-1", max_attempts=3
    )
    calls: list[str] = []
    assert consumer.run_once(lambda event: calls.append(event.event_id)).processed == 1
    assert consumer.run_once(lambda event: calls.append(event.event_id)).read == 0
    # A second consumer can still receive the same provider event only if the
    # provider redelivers it; the Inbox remains the business idempotency guard.
    assert calls == ["evt-1"]


def test_transient_failure_is_retried_and_eventually_processed() -> None:
    bus = InMemoryEventBus()
    inbox = InMemoryInboxStore()
    bus.publish(EventEnvelope("evt-2", "quality.case.opened.v1", datetime.now(UTC), {}))
    consumer = ReliableEventConsumer(
        bus, inbox, consumer_group="investigation", consumer_name="worker-1", max_attempts=3
    )
    attempts = 0

    def handler(_: EventEnvelope) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise RuntimeError("temporary database timeout")

    first = consumer.run_once(handler)
    second = consumer.run_once(handler)
    assert first.retried == 1
    assert second.processed == 1
    assert attempts == 2
    assert bus.pending_count("investigation") == 0


def test_permanent_failure_goes_to_dlq_and_reports_backlog() -> None:
    bus = InMemoryEventBus()
    inbox = InMemoryInboxStore()
    bus.publish(EventEnvelope("evt-3", "quality.case.opened.v1", datetime.now(UTC), {}))
    consumer = ReliableEventConsumer(
        bus, inbox, consumer_group="investigation", consumer_name="worker-1", max_attempts=5
    )
    result = consumer.run_once(lambda _: (_ for _ in ()).throw(PermanentEventError("bad schema")))
    assert result.dead_lettered == 1
    assert len(bus.dead_letters) == 1
    assert bus.pending_count("investigation") == 0
