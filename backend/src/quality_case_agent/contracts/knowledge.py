"""Versioned knowledge ingestion and retrieval contracts."""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from .common import ContractModel, to_utc


class KnowledgeDocumentContract(ContractModel):
    """Minimum metadata required before a document can be indexed."""

    document_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    version: str = Field(min_length=1, max_length=64)
    source_type: Literal["TECHNICAL_DOCUMENT", "VERIFIED_CASE"]
    content: str = Field(min_length=1, max_length=200_000)
    effective_from: datetime
    effective_to: datetime | None = None
    applicability: dict[str, str] = Field(min_length=1)
    status: Literal["ACTIVE", "SUPERSEDED"] = "ACTIVE"

    @field_validator("effective_from", "effective_to")
    @classmethod
    def normalize_dates(cls, value: datetime | None) -> datetime | None:
        return None if value is None else to_utc(value)


class KnowledgeDocumentUploadContract(ContractModel):
    """Metadata submitted alongside a Markdown or PDF upload."""

    document_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    version: str = Field(min_length=1, max_length=64)
    source_type: Literal["TECHNICAL_DOCUMENT", "VERIFIED_CASE"]
    file_name: str = Field(min_length=1, max_length=256)
    content_type: Literal["text/markdown", "text/plain", "application/pdf"]
    effective_from: datetime
    effective_to: datetime | None = None
    applicability: dict[str, str] = Field(min_length=1)

    @field_validator("effective_from", "effective_to")
    @classmethod
    def normalize_dates(cls, value: datetime | None) -> datetime | None:
        return None if value is None else to_utc(value)


class KnowledgeTextUploadContract(KnowledgeDocumentUploadContract):
    """JSON-friendly upload form used by the local API and demo UI."""

    content: str = Field(min_length=1, max_length=200_000)


class KnowledgeIngestionReceiptContract(ContractModel):
    document_id: str
    content_sha256: str = Field(min_length=64, max_length=64)
    chunk_count: int = Field(ge=1)
    duplicate: bool


class KnowledgeSearchHitContract(ContractModel):
    evidence_id: str
    document_id: str
    title: str
    version: str
    source_type: Literal["TECHNICAL_DOCUMENT", "VERIFIED_CASE"]
    section: str
    page: int | None = Field(default=None, ge=1)
    content: str
    retrieval_score: float = Field(ge=0.0, le=1.0)
    applicability: Literal["APPLICABLE", "NOT_APPLICABLE"]
    applicability_reasons: list[str] = Field(default_factory=list)
    source_metadata: dict[str, str] = Field(default_factory=dict)


class CaseArchivedEventContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    event_id: str
    event_type: Literal["quality.case.archived.v1"] = "quality.case.archived.v1"
    occurred_at: datetime
    case_id: str
    archive_uri: str
    knowledge_index_status: Literal["INDEXED", "NOT_ELIGIBLE"]
    knowledge_document_id: str | None = None
    content_hash: str

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime) -> datetime:
        return to_utc(value)
