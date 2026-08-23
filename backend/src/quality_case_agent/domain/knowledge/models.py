"""Pure knowledge-base value objects used by ingestion and retrieval ports."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class DocumentSection:
    """Parser output retained so search results can cite a section and page."""

    section: str
    content: str
    page: int | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """A versioned, auditable source document."""

    document_id: str
    title: str
    version: str
    source_type: str
    content: str
    effective_from: datetime
    effective_to: datetime | None
    applicability: Mapping[str, str]
    status: str = "ACTIVE"
    content_sha256: str = ""
    sections: tuple[DocumentSection, ...] = ()

    def __post_init__(self) -> None:
        if not self.document_id or not self.title or not self.version:
            raise ValueError("document_id, title and version are required")
        if not self.content.strip():
            raise ValueError("document content must not be empty")
        if self.status not in {"ACTIVE", "SUPERSEDED"}:
            raise ValueError("status must be ACTIVE or SUPERSEDED")
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")
        object.__setattr__(self, "applicability", MappingProxyType(dict(self.applicability)))


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    """A searchable chunk retaining its source citation metadata."""

    evidence_id: str
    document_id: str
    title: str
    version: str
    source_type: str
    section: str
    page: int | None
    content: str
    effective_from: datetime
    effective_to: datetime | None
    status: str
    applicability: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "applicability", MappingProxyType(dict(self.applicability)))


@dataclass(frozen=True, slots=True)
class KnowledgeSearchQuery:
    query: str
    source_types: tuple[str, ...]
    filters: Mapping[str, str]
    top_k: int = 5
    effective_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("query must not be empty")
        if not 1 <= self.top_k <= 20:
            raise ValueError("top_k must be between 1 and 20")
        object.__setattr__(self, "filters", MappingProxyType(dict(self.filters)))


@dataclass(frozen=True, slots=True)
class KnowledgeSearchHit:
    chunk: KnowledgeChunk
    score: float
    applicability_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class KnowledgeIngestionReceipt:
    document_id: str
    content_sha256: str
    chunk_count: int
    duplicate: bool


@dataclass(frozen=True, slots=True)
class VerifiedCaseIndexRecord:
    document_id: str
    text: str
    metadata: Mapping[str, str]
    content_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
