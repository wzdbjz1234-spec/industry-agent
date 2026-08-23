"""Deterministic in-memory lexical knowledge-base adapter.

The adapter deliberately exposes the same Port a pgvector adapter will use later,
but has no network, database or embedding-service dependency.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from math import sqrt

from quality_case_agent.application.ports.knowledge import EmbeddingProvider
from quality_case_agent.domain.knowledge.models import (
    DocumentSection,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIngestionReceipt,
    KnowledgeSearchHit,
    KnowledgeSearchQuery,
)

_CJK = re.compile(r"[\u3400-\u9fff]")
_WORD = re.compile(r"[a-z0-9_]+")


def _tokens(text: str) -> set[str]:
    lowered = text.lower()
    tokens = set(_WORD.findall(lowered))
    cjk = "".join(_CJK.findall(lowered))
    tokens.update(cjk)
    tokens.update(cjk[index : index + 2] for index in range(max(0, len(cjk) - 1)))
    return tokens


class InMemoryKnowledgeBase:
    """Metadata-filtered local retrieval with a replaceable embedding seam.

    Lexical overlap remains part of the score so the adapter is useful without a network
    dependency. When an embedding provider is supplied, cosine similarity is blended into the
    score and stored per chunk exactly as a pgvector adapter would store it.
    """

    def __init__(self, embedding_provider: EmbeddingProvider | None = None) -> None:
        self._documents: dict[str, KnowledgeDocument] = {}
        self._hashes: dict[str, str] = {}
        self._chunks: dict[str, KnowledgeChunk] = {}
        self._embedding_provider = embedding_provider
        self._embeddings: dict[str, tuple[float, ...]] = {}

    def ingest(self, document: KnowledgeDocument) -> KnowledgeIngestionReceipt:
        content_hash = hashlib.sha256(document.content.encode("utf-8")).hexdigest()
        existing_id = self._hashes.get(content_hash)
        if existing_id is not None:
            count = sum(chunk.document_id == existing_id for chunk in self._chunks.values())
            return KnowledgeIngestionReceipt(existing_id, content_hash, count, True)
        if document.document_id in self._documents:
            raise ValueError(
                f"document_id already exists with different content: {document.document_id}"
            )

        self._documents[document.document_id] = document
        self._hashes[content_hash] = document.document_id
        chunks = split_document(document)
        self._chunks.update({chunk.evidence_id: chunk for chunk in chunks})
        if self._embedding_provider is not None:
            self._embeddings.update(
                {
                    chunk.evidence_id: self._embedding_provider.embed(chunk.content)
                    for chunk in chunks
                }
            )
        return KnowledgeIngestionReceipt(document.document_id, content_hash, len(chunks), False)

    def supersede(self, document_id: str) -> None:
        document = self._documents.get(document_id)
        if document is None:
            raise KeyError(document_id)
        self._documents[document_id] = KnowledgeDocument(
            document_id=document.document_id,
            title=document.title,
            version=document.version,
            source_type=document.source_type,
            content=document.content,
            effective_from=document.effective_from,
            effective_to=document.effective_to,
            applicability=document.applicability,
            status="SUPERSEDED",
            content_sha256=document.content_sha256,
        )
        for evidence_id, chunk in tuple(self._chunks.items()):
            if chunk.document_id == document_id:
                self._chunks[evidence_id] = KnowledgeChunk(
                    evidence_id=chunk.evidence_id,
                    document_id=chunk.document_id,
                    title=chunk.title,
                    version=chunk.version,
                    source_type=chunk.source_type,
                    section=chunk.section,
                    page=chunk.page,
                    content=chunk.content,
                    effective_from=chunk.effective_from,
                    effective_to=chunk.effective_to,
                    status="SUPERSEDED",
                    applicability=chunk.applicability,
                )

    def search(self, query: KnowledgeSearchQuery) -> Sequence[KnowledgeSearchHit]:
        query_tokens = _tokens(query.query)
        query_embedding = (
            self._embedding_provider.embed(query.query)
            if self._embedding_provider is not None
            else None
        )
        candidates: list[KnowledgeSearchHit] = []
        for chunk in self._chunks.values():
            if chunk.status != "ACTIVE":
                continue
            if not self._is_retrievable_verified_case(chunk):
                continue
            if query.source_types and chunk.source_type not in query.source_types:
                continue
            if not self._is_effective(chunk, query.effective_at):
                continue
            applicable, reasons = self._applicability(chunk, query.filters)
            if not applicable:
                continue
            overlap = len(query_tokens & _tokens(chunk.content))
            semantic_score = (
                _cosine(query_embedding, self._embeddings.get(chunk.evidence_id))
                if query_embedding is not None
                else 0.0
            )
            if overlap == 0 and semantic_score <= 0.0:
                continue
            lexical_score = overlap / max(1, len(query_tokens))
            score = min(1.0, 0.7 * semantic_score + 0.3 * lexical_score)
            candidates.append(KnowledgeSearchHit(chunk, score, tuple(reasons)))
        return tuple(
            sorted(
                candidates,
                key=lambda hit: (-hit.score, hit.chunk.document_id, hit.chunk.evidence_id),
            )[: query.top_k]
        )

    @staticmethod
    def _is_retrievable_verified_case(chunk: KnowledgeChunk) -> bool:
        """Keep the trusted-case boundary at the retrieval adapter.

        Phase 3 fixtures used a bare ``VERIFIED_CASE`` document before the archive
        workflow existed. Those documents remain readable for backwards-compatible
        offline tests. Records produced by the archive promotion path carry the
        trust metadata below and must satisfy both lifecycle predicates.
        """

        if chunk.source_type != "VERIFIED_CASE":
            return True
        metadata = chunk.applicability
        if "case_status" not in metadata and "verification_status" not in metadata:
            return True
        return (
            metadata.get("case_status") == "CONFIRMED"
            and metadata.get("verification_status") == "VERIFIED_EFFECTIVE"
        )

    @staticmethod
    def _is_effective(chunk: KnowledgeChunk, effective_at: datetime | None) -> bool:
        if effective_at is None:
            effective_at = datetime.now(UTC)
        return chunk.effective_from <= effective_at and (
            chunk.effective_to is None or effective_at < chunk.effective_to
        )

    @staticmethod
    def _applicability(chunk: KnowledgeChunk, filters: Mapping[str, str]) -> tuple[bool, list[str]]:
        filter_mapping: dict[str, str] = dict(filters)
        reasons: list[str] = []
        legacy_case = (
            chunk.source_type == "VERIFIED_CASE"
            and "case_status" not in chunk.applicability
            and "verification_status" not in chunk.applicability
        )
        for key, value in sorted(filter_mapping.items()):
            actual = chunk.applicability.get(key)
            if actual is None:
                if (
                    (legacy_case and key not in {"station_id", "product_id"})
                    or (chunk.source_type != "VERIFIED_CASE" and key in {
                        "trigger_family",
                        "date_prefix",
                        "case_status",
                        "verification_status",
                        "archive_uri",
                    })
                ):
                    reasons.append(f"该来源未提供{key}元数据，使用来源特定过滤")
                    continue
                return False, []
            if actual != value:
                return False, []
            reasons.append(f"适用于{key}={value}")
        return True, reasons or ["通过状态和生效时间过滤"]

    @staticmethod
    def _split(document: KnowledgeDocument) -> tuple[KnowledgeChunk, ...]:
        return split_document(document)


def split_document(document: KnowledgeDocument) -> tuple[KnowledgeChunk, ...]:
    """Turn parser sections (or plain text paragraphs) into citation-ready chunks."""

    chunks: list[KnowledgeChunk] = []
    document_sections = getattr(document, "sections", ())
    if document_sections:
        sections = document_sections
    else:
        raw_sections = [part.strip() for part in document.content.split("\n\n") if part.strip()]
        if not raw_sections:
            raw_sections = [document.content.strip()]
        sections = tuple(
            DocumentSection(
                section=(content.splitlines()[0].strip().lstrip("# ")[:128] or f"section-{index}"),
                content=content,
                page=index,
            )
            for index, content in enumerate(raw_sections, start=1)
        )
    for index, item in enumerate(sections, start=1):
        content = item.content.strip()
        if not content:
            continue
        chunks.append(
            KnowledgeChunk(
                evidence_id=f"{document.document_id}:chunk-{index:04d}",
                document_id=document.document_id,
                title=document.title,
                version=document.version,
                source_type=document.source_type,
                section=item.section,
                page=item.page or index,
                content=content,
                effective_from=document.effective_from,
                effective_to=document.effective_to,
                status=document.status,
                applicability=document.applicability,
            )
        )
    return tuple(chunks)


def _cosine(left: tuple[float, ...] | None, right: tuple[float, ...] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    denominator = sqrt(sum(a * a for a in left) * sum(b * b for b in right))
    if denominator == 0:
        return 0.0
    return max(0.0, min(1.0, numerator / denominator))
