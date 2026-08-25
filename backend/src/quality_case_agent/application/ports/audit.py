"""Append-only audit log seam."""

from collections.abc import Sequence
from typing import Protocol

from quality_case_agent.contracts.identity import AuditEventContract


class AuditLog(Protocol):
    def append(self, event: AuditEventContract) -> AuditEventContract:
        """Append exactly once by event ID and reject conflicting payloads."""

    def list_events(self, *, limit: int = 200) -> Sequence[AuditEventContract]:
        """Return newest events without allowing mutation."""

    def verify_chain(self) -> bool:
        """Verify the append-only hash chain."""

    def export_jsonl(self) -> str:
        """Export a redacted, newline-delimited immutable audit stream."""
