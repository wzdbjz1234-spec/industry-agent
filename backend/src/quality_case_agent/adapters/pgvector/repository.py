"""PostgreSQL/pgvector repository seam.

The repository deliberately depends on a tiny executor protocol instead of SQLAlchemy. This keeps
the adapter importable in offline tests while allowing the production composition root to provide
an async or synchronous PostgreSQL executor later.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Protocol

from quality_case_agent.adapters.in_memory.knowledge import split_document
from quality_case_agent.application.ports.knowledge import EmbeddingProvider
from quality_case_agent.domain.knowledge.models import (
    KnowledgeDocument,
    KnowledgeIngestionReceipt,
    KnowledgeSearchHit,
    KnowledgeSearchQuery,
)


class PgVectorExecutor(Protocol):
    def fetch_one(self, statement: str, parameters: Mapping[str, object]) -> Mapping[str, object] | None:
        """Fetch one row using the application's database session boundary."""

    def fetch_all(self, statement: str, parameters: Mapping[str, object]) -> Sequence[Mapping[str, object]]:
        """Fetch rows using the application's database session boundary."""

    def execute(self, statement: str, parameters: Mapping[str, object]) -> None:
        """Execute one parameterized statement."""


class PgVectorKnowledgeBase:
    """Store and search chunks in a PostgreSQL table with a pgvector column."""

    def __init__(self, executor: PgVectorExecutor, embedding_provider: EmbeddingProvider) -> None:
        self._executor = executor
        self._embedding_provider = embedding_provider

    def ingest(self, document: KnowledgeDocument) -> KnowledgeIngestionReceipt:
        content_hash = hashlib.sha256(document.content.encode("utf-8")).hexdigest()
        duplicate = self._executor.fetch_one(
            "SELECT document_id, chunk_count FROM knowledge_documents "
            "WHERE content_sha256 = :content_sha256",
            {"content_sha256": content_hash},
        )
        if duplicate is not None:
            return KnowledgeIngestionReceipt(
                str(duplicate["document_id"]),
                content_hash,
                _as_int(duplicate.get("chunk_count"), "chunk_count"),
                True,
            )
        existing_id = self._executor.fetch_one(
            "SELECT document_id FROM knowledge_documents WHERE document_id = :document_id",
            {"document_id": document.document_id},
        )
        if existing_id is not None:
            raise ValueError(f"document_id already exists: {document.document_id}")

        chunks = split_document(document)
        self._executor.execute(
            "INSERT INTO knowledge_documents "
            "(document_id, title, version, source_type, effective_from, effective_to, "
            "applicability, status, content_sha256, chunk_count) VALUES "
            "(:document_id, :title, :version, :source_type, :effective_from, :effective_to, "
            ":applicability, :status, :content_sha256, :chunk_count)",
            {
                "document_id": document.document_id,
                "title": document.title,
                "version": document.version,
                "source_type": document.source_type,
                "effective_from": document.effective_from,
                "effective_to": document.effective_to,
                "applicability": dict(document.applicability),
                "status": document.status,
                "content_sha256": content_hash,
                "chunk_count": len(chunks),
            },
        )
        for chunk in chunks:
            self._executor.execute(
                "INSERT INTO knowledge_chunks "
                "(evidence_id, document_id, section, page, content, embedding) VALUES "
                "(:evidence_id, :document_id, :section, :page, :content, :embedding)",
                {
                    "evidence_id": chunk.evidence_id,
                    "document_id": chunk.document_id,
                    "section": chunk.section,
                    "page": chunk.page,
                    "content": chunk.content,
                    "embedding": self._embedding_provider.embed(chunk.content),
                },
            )
        return KnowledgeIngestionReceipt(document.document_id, content_hash, len(chunks), False)

    def supersede(self, document_id: str) -> None:
        self._executor.execute(
            "UPDATE knowledge_documents SET status = 'SUPERSEDED' WHERE document_id = :document_id",
            {"document_id": document_id},
        )

    def search(self, query: KnowledgeSearchQuery) -> Sequence[KnowledgeSearchHit]:
        filters = dict(query.filters)
        parameters: dict[str, object] = {
            "query_embedding": self._embedding_provider.embed(query.query),
            "top_k": query.top_k,
            "source_types": list(query.source_types),
            "source_types_empty": not query.source_types,
            "effective_at": query.effective_at,
            "filters_json": json.dumps(filters, ensure_ascii=False),
            "trusted_case_status_json": json.dumps(
                {
                    "case_status": "CONFIRMED",
                    "verification_status": "VERIFIED_EFFECTIVE",
                }
            ),
        }
        rows = self._executor.fetch_all(
            "SELECT c.evidence_id, c.document_id, d.title, d.version, d.source_type, c.section, c.page, "
            "c.content, d.effective_from, d.effective_to, 1 - (c.embedding <=> :query_embedding) AS score, d.applicability "
            "FROM knowledge_chunks c JOIN knowledge_documents d USING (document_id) "
            "WHERE d.status = 'ACTIVE' "
            "AND (:source_types_empty OR d.source_type = ANY(:source_types)) "
            "AND (:effective_at IS NULL OR d.effective_from <= :effective_at) "
            "AND (:effective_at IS NULL OR d.effective_to IS NULL OR :effective_at < d.effective_to) "
            "AND (d.source_type <> 'VERIFIED_CASE' OR ("
            "d.applicability @> CAST(:trusted_case_status_json AS jsonb))) "
            "AND d.applicability @> CAST(:filters_json AS jsonb) "
            "ORDER BY c.embedding <=> :query_embedding LIMIT :top_k",
            parameters,
        )
        from quality_case_agent.domain.knowledge.models import KnowledgeChunk

        return tuple(
            KnowledgeSearchHit(
                KnowledgeChunk(
                    evidence_id=str(row["evidence_id"]),
                    document_id=str(row["document_id"]),
                    title=str(row["title"]),
                    version=str(row["version"]),
                    source_type=str(row["source_type"]),
                    section=str(row["section"]),
                    page=_as_int(row.get("page"), "page") if row.get("page") is not None else None,
                    content=str(row["content"]),
                    effective_from=_as_datetime(row.get("effective_from")),
                    effective_to=_as_optional_datetime(row.get("effective_to")),
                    status="ACTIVE",
                    applicability=_as_mapping(row.get("applicability", {})),
                ),
                max(0.0, min(1.0, _as_float(row.get("score"), "score"))),
                ("通过ACTIVE、生效时间和适用范围过滤",),
            )
            for row in rows
        )


def _as_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise TypeError(f"pgvector row {label} is not an integer")
    return int(value)


def _as_float(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int, str)):
        raise TypeError(f"pgvector row {label} is not numeric")
    return float(value)


def _as_datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        return document_effective_fallback()
    return value


def _as_optional_datetime(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _as_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def document_effective_fallback() -> datetime:
    """Return a timezone-aware sentinel for rows whose query omits an as-of date."""

    return datetime(1970, 1, 1, tzinfo=UTC)
