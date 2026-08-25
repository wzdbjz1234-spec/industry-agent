"""SQLAlchemy append-only audit adapter for production runtime resources."""

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast

from sqlalchemy import Column, String, Table, Text, insert, select

from quality_case_agent.adapters.in_memory.audit import InMemoryAuditLog
from quality_case_agent.adapters.postgres.repositories import SqlAlchemyPersistence, metadata
from quality_case_agent.contracts.identity import AuditEventContract

audit_events = Table(
    "audit_events",
    metadata,
    Column("event_id", String(160), primary_key=True),
    Column("event_type", String(128), nullable=False),
    Column("occurred_at", String(64), nullable=False),
    Column("actor_id", String(128), nullable=False),
    Column("roles", Text, nullable=False),
    Column("organization", String(256), nullable=False),
    Column("action", String(128), nullable=False),
    Column("resource_type", String(128), nullable=False),
    Column("resource_id", String(160), nullable=False),
    Column("correlation_id", String(160), nullable=False),
    Column("causation_id", String(160)),
    Column("trace_id", String(160)),
    Column("policy_version", String(64), nullable=False),
    Column("claims_digest", String(128), nullable=False),
    Column("metadata", Text, nullable=False),
    Column("previous_hash", String(128)),
    Column("event_hash", String(128), nullable=False, unique=True),
)


class SqlAlchemyAuditLog:
    def __init__(self, persistence: SqlAlchemyPersistence) -> None:
        self._db = persistence
        metadata.create_all(self._db.engine)

    def append(self, event: AuditEventContract) -> AuditEventContract:
        with self._db.begin() as conn:
            existing = conn.execute(
                select(audit_events).where(audit_events.c.event_id == event.event_id)
            ).mappings().first()
            if existing is not None:
                saved = self._from_row(existing)
                if saved != event:
                    raise ValueError(f"audit event ID already contains different payload: {event.event_id}")
                return saved
            previous = conn.execute(
                select(audit_events.c.event_hash)
                .order_by(audit_events.c.occurred_at.desc(), audit_events.c.event_id.desc())
                .limit(1)
            ).scalar_one_or_none()
            if event.previous_hash != previous:
                raise ValueError("audit event previous_hash does not match the append chain")
            if event.event_hash != InMemoryAuditLog.compute_hash(event):
                raise ValueError("audit event hash is invalid")
            conn.execute(insert(audit_events).values(**self._values(event)))
        return event

    def list_events(self, *, limit: int = 200) -> Sequence[AuditEventContract]:
        if limit < 1 or limit > 1_000:
            raise ValueError("audit limit must be between 1 and 1000")
        with self._db.engine.connect() as conn:
            rows = conn.execute(
                select(audit_events)
                .order_by(audit_events.c.occurred_at.desc(), audit_events.c.event_id.desc())
                .limit(limit)
            ).mappings()
            return tuple(self._from_row(row) for row in rows)

    def verify_chain(self) -> bool:
        with self._db.engine.connect() as conn:
            rows = conn.execute(
                select(audit_events).order_by(audit_events.c.occurred_at, audit_events.c.event_id)
            ).mappings()
            previous: str | None = None
            for row in rows:
                event = self._from_row(row)
                if event.previous_hash != previous or event.event_hash != InMemoryAuditLog.compute_hash(event):
                    return False
                previous = event.event_hash
        return True

    def export_jsonl(self) -> str:
        return "\n".join(
            json.dumps(event.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
            for event in self.list_events(limit=1_000)[::-1]
        )

    @staticmethod
    def _values(event: AuditEventContract) -> dict[str, object]:
        return {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "occurred_at": event.occurred_at.isoformat(),
            "actor_id": event.actor_id,
            "roles": json.dumps(event.roles, ensure_ascii=False),
            "organization": event.organization,
            "action": event.action,
            "resource_type": event.resource_type,
            "resource_id": event.resource_id,
            "correlation_id": event.correlation_id,
            "causation_id": event.causation_id,
            "trace_id": event.trace_id,
            "policy_version": event.policy_version,
            "claims_digest": event.claims_digest,
            "metadata": json.dumps(event.metadata, ensure_ascii=False, sort_keys=True),
            "previous_hash": event.previous_hash,
            "event_hash": event.event_hash,
        }

    @staticmethod
    def _from_row(row: object) -> AuditEventContract:
        value = cast(dict[str, Any], row)
        return AuditEventContract(
            event_id=str(value["event_id"]),
            event_type=str(value["event_type"]),
            occurred_at=datetime.fromisoformat(str(value["occurred_at"])),
            actor_id=str(value["actor_id"]),
            roles=json.loads(str(value["roles"])),
            organization=str(value["organization"]),
            action=str(value["action"]),
            resource_type=str(value["resource_type"]),
            resource_id=str(value["resource_id"]),
            correlation_id=str(value["correlation_id"]),
            causation_id=str(value["causation_id"]) if value["causation_id"] is not None else None,
            trace_id=str(value["trace_id"]) if value["trace_id"] is not None else None,
            policy_version=str(value["policy_version"]),
            claims_digest=str(value["claims_digest"]),
            metadata=json.loads(str(value["metadata"])),
            previous_hash=str(value["previous_hash"]) if value["previous_hash"] is not None else None,
            event_hash=str(value["event_hash"]),
        )
