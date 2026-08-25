"""Redis Streams EventBus adapter.

The adapter maps Redis IDs and pending entries to the provider-neutral eventing
port.  Redis is imported lazily so offline unit tests do not need a server.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast

from quality_case_agent.application.ports.event_bus import EventBus, EventDelivery, EventEnvelope


class RedisStreamsEventBus(EventBus):
    def __init__(self, redis_client: Any, *, stream: str = "quality-events", visibility_timeout_ms: int = 30_000) -> None:
        self.redis = redis_client
        self.stream = stream
        self.visibility_timeout_ms = visibility_timeout_ms

    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        stream: str = "quality-events",
        visibility_timeout_ms: int = 30_000,
    ) -> RedisStreamsEventBus:
        from redis import Redis

        return cls(
            Redis.from_url(url, decode_responses=True),
            stream=stream,
            visibility_timeout_ms=visibility_timeout_ms,
        )

    def publish(self, envelope: EventEnvelope) -> str:
        return str(self.redis.xadd(envelope.stream, {
            "event_id": envelope.event_id,
            "event_type": envelope.event_type,
            "occurred_at": envelope.occurred_at.isoformat(),
            "payload": json.dumps(envelope.payload, sort_keys=True),
        }))

    def _ensure_group(self, group: str) -> None:
        try:
            self.redis.xgroup_create(self.stream, group, id="0-0", mkstream=True)
        except Exception as exc:  # redis-py exposes ResponseError; keep adapter import-light
            if "BUSYGROUP" not in str(exc):
                raise

    def read(self, consumer_group: str, consumer_name: str, *, limit: int = 10) -> tuple[EventDelivery, ...]:
        self._ensure_group(consumer_group)
        now = datetime.now(UTC)
        deliveries: list[EventDelivery] = []
        # First reclaim entries left pending by a crashed consumer. Redis returns
        # (next_start_id, entries, deleted_ids) for XAUTOCLAIM.
        claimed = self.redis.xautoclaim(
            self.stream,
            consumer_group,
            consumer_name,
            min_idle_time=self.visibility_timeout_ms,
            start_id="0-0",
            count=limit,
        )
        entries = claimed[1] if isinstance(claimed, (tuple, list)) and len(claimed) > 1 else ()
        deliveries.extend(self._to_deliveries(entries, consumer_group, consumer_name, now, attempts=2))
        remaining = max(0, limit - len(deliveries))
        if remaining:
            response = self.redis.xreadgroup(
                consumer_group, consumer_name, {self.stream: ">"}, count=remaining, block=1
            )
            for stream_name, new_entries in response or ():
                deliveries.extend(
                    self._to_deliveries(new_entries, consumer_group, consumer_name, now, attempts=1, stream_name=str(stream_name))
                )
        return tuple(deliveries)

    def _to_deliveries(
        self,
        entries: object,
        consumer_group: str,
        consumer_name: str,
        delivered_at: datetime,
        *,
        attempts: int,
        stream_name: str | None = None,
    ) -> list[EventDelivery]:
        result: list[EventDelivery] = []
        raw_entries = cast(list[tuple[object, Any]], entries) if isinstance(entries, (list, tuple)) else []
        for message_id, fields in raw_entries:
            result.append(EventDelivery(
                delivery_id=str(message_id),
                envelope=EventEnvelope(
                    event_id=str(fields["event_id"]),
                    event_type=str(fields["event_type"]),
                    occurred_at=datetime.fromisoformat(str(fields["occurred_at"])),
                    payload=json.loads(str(fields["payload"])),
                    stream=stream_name or self.stream,
                ),
                consumer_group=consumer_group,
                consumer_name=consumer_name,
                delivered_at=delivered_at,
                attempts=attempts,
            ))
        return result

    def ack(self, delivery: EventDelivery) -> None:
        self.redis.xack(delivery.envelope.stream, delivery.consumer_group, delivery.delivery_id)

    def retry(self, delivery: EventDelivery, *, error: str, max_attempts: int) -> bool:
        if delivery.attempts >= max_attempts:
            self.redis.xadd(f"{delivery.envelope.stream}:dlq", {
                "event_id": delivery.envelope.event_id,
                "event_type": delivery.envelope.event_type,
                "payload": json.dumps(delivery.envelope.payload, sort_keys=True),
                "error": error[:512],
            })
            self.ack(delivery)
            return True
        # Leave the entry pending. A subsequent recovery/claim cycle will retry it.
        return False

    def pending_count(self, consumer_group: str) -> int:
        self._ensure_group(consumer_group)
        summary = self.redis.xpending(self.stream, consumer_group)
        return int(summary.get("pending", 0)) if isinstance(summary, dict) else int(summary[0])

    def oldest_pending_age_seconds(self, consumer_group: str) -> float:
        self._ensure_group(consumer_group)
        summary = self.redis.xpending_range(self.stream, consumer_group, min="-", max="+", count=1)
        if not summary:
            return 0.0
        idle = summary[0].get("time_since_delivered", summary[0].get("idle", 0))
        return float(idle) / 1000.0
