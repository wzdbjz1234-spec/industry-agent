"""Ports for immutable Case archive and trusted-case indexing."""

from collections.abc import Sequence
from typing import Protocol

from quality_case_agent.domain.knowledge.models import VerifiedCaseIndexRecord


class CaseArchiveStore(Protocol):
    def put(self, uri: str, payload: bytes, content_sha256: str) -> bool:
        """Store a new immutable object; return False for an identical duplicate."""


class VerifiedCaseIndex(Protocol):
    def index(self, record: VerifiedCaseIndexRecord) -> bool:
        """Index once by document ID and hash; return whether a new record was added."""

    def list_records(self) -> Sequence[VerifiedCaseIndexRecord]:
        """Return indexed records for audit and tests."""
