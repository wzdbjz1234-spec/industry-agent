"""Immutable local archive and trusted-case index adapters."""

from collections.abc import Sequence

from quality_case_agent.domain.knowledge.models import VerifiedCaseIndexRecord


class InMemoryCaseArchiveStore:
    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str]] = {}

    def put(self, uri: str, payload: bytes, content_sha256: str) -> bool:
        existing = self._objects.get(uri)
        if existing is not None:
            if existing[1] != content_sha256:
                raise ValueError("archive URI is immutable and cannot be overwritten")
            return False
        self._objects[uri] = (payload, content_sha256)
        return True

    def get(self, uri: str) -> bytes:
        return self._objects[uri][0]

    @property
    def object_count(self) -> int:
        return len(self._objects)


class InMemoryVerifiedCaseIndex:
    def __init__(self) -> None:
        self._records: dict[str, VerifiedCaseIndexRecord] = {}

    def index(self, record: VerifiedCaseIndexRecord) -> bool:
        existing = self._records.get(record.document_id)
        if existing is not None:
            if existing.content_sha256 != record.content_sha256:
                raise ValueError("verified case index document is immutable")
            return False
        self._records[record.document_id] = record
        return True

    def list_records(self) -> Sequence[VerifiedCaseIndexRecord]:
        return tuple(sorted(self._records.values(), key=lambda record: record.document_id))
