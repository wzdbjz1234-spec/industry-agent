"""Hash-chained append-only audit adapter for demo, tests and shadow mode."""

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime

from quality_case_agent.contracts.identity import AuditEventContract


class InMemoryAuditLog:
    def __init__(self) -> None:
        self._events: dict[str, AuditEventContract] = {}
        self._order: list[str] = []

    def append(self, event: AuditEventContract) -> AuditEventContract:
        existing = self._events.get(event.event_id)
        if existing is not None:
            if existing != event:
                raise ValueError(f"audit event ID already contains different payload: {event.event_id}")
            return existing
        previous_hash = self._events[self._order[-1]].event_hash if self._order else None
        if event.previous_hash != previous_hash:
            raise ValueError("audit event previous_hash does not match the append chain")
        if event.event_hash != self.compute_hash(event):
            raise ValueError("audit event hash is invalid")
        self._events[event.event_id] = event
        self._order.append(event.event_id)
        return event

    def list_events(self, *, limit: int = 200) -> Sequence[AuditEventContract]:
        if limit < 1 or limit > 1_000:
            raise ValueError("audit limit must be between 1 and 1000")
        return tuple(self._events[event_id] for event_id in self._order[-limit:][::-1])

    def verify_chain(self) -> bool:
        previous: str | None = None
        for event_id in self._order:
            event = self._events[event_id]
            if event.previous_hash != previous or event.event_hash != self.compute_hash(event):
                return False
            previous = event.event_hash
        return True

    def export_jsonl(self) -> str:
        return "\n".join(
            json.dumps(self._events[event_id].model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
            for event_id in self._order
        )

    @staticmethod
    def compute_hash(event: AuditEventContract) -> str:
        payload = event.model_dump(mode="json")
        payload.pop("event_hash", None)
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def audit_now() -> datetime:
    return datetime.now(UTC)
