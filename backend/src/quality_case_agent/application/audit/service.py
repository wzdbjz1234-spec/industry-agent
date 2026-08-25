"""Create redacted, hash-chained audit events behind one small interface."""

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from quality_case_agent.adapters.in_memory.audit import InMemoryAuditLog
from quality_case_agent.application.ports.audit import AuditLog
from quality_case_agent.contracts.identity import AuditEventContract, IdentityContract


class AuditService:
    def __init__(self, log: AuditLog, *, policy_version: str = "identity-policy-v1") -> None:
        self._log = log
        self._policy_version = policy_version
        self._known: dict[str, AuditEventContract] = {}

    def record(
        self,
        identity: IdentityContract,
        *,
        event_type: str,
        action: str,
        resource_type: str,
        resource_id: str,
        correlation_id: str,
        causation_id: str | None = None,
        trace_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
        occurred_at: datetime | None = None,
    ) -> AuditEventContract:
        safe_metadata = self.redact_mapping(metadata or {})
        event_id = f"audit-{uuid5(NAMESPACE_URL, f'{event_type}:{action}:{resource_type}:{resource_id}:{correlation_id}').hex[:24]}"
        existing = self._known.get(event_id)
        if existing is not None:
            return existing
        previous = next(iter(self._log.list_events(limit=1)), None)
        previous_hash = previous.event_hash if previous is not None else None
        event = AuditEventContract(
            event_id=event_id,
            event_type=event_type,
            occurred_at=(occurred_at or datetime.now(UTC)).astimezone(UTC),
            actor_id=identity.actor_id,
            roles=identity.roles,
            organization=identity.organization,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            trace_id=trace_id,
            policy_version=self._policy_version,
            claims_digest=identity.claims_digest,
            metadata=safe_metadata,
            previous_hash=previous_hash,
            event_hash="0" * 64,
        )
        event_hash = InMemoryAuditLog.compute_hash(event)
        saved = self._log.append(event.model_copy(update={"event_hash": event_hash}))
        self._known[event_id] = saved
        return saved

    @classmethod
    def redact_mapping(cls, value: Mapping[str, object]) -> dict[str, object]:
        return {str(key): cls._redact(item, str(key).lower()) for key, item in value.items()}

    @classmethod
    def _redact(cls, value: object, key: str = "") -> object:
        if any(marker in key for marker in ("secret", "token", "password", "api_key", "signature")):
            return "[REDACTED]"
        if isinstance(value, Mapping):
            return {str(item_key): cls._redact(item, str(item_key).lower()) for item_key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._redact(item, key) for item in value]
        if isinstance(value, str):
            return value[:2_000]
        return value
