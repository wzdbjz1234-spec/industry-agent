"""Map boundary contracts to the replaceable knowledge-base port."""

from collections.abc import Sequence
from datetime import datetime
from typing import Literal, cast

from quality_case_agent.application.ports.knowledge import DocumentParser, KnowledgeBase
from quality_case_agent.contracts.knowledge import (
    KnowledgeDocumentContract,
    KnowledgeDocumentUploadContract,
    KnowledgeIngestionReceiptContract,
    KnowledgeSearchHitContract,
)
from quality_case_agent.domain.knowledge.models import (
    KnowledgeDocument,
    KnowledgeSearchQuery,
)


class KnowledgeService:
    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self._knowledge_base = knowledge_base

    def ingest(self, document: KnowledgeDocumentContract) -> KnowledgeIngestionReceiptContract:
        receipt = self._knowledge_base.ingest(
            KnowledgeDocument(
                document_id=document.document_id,
                title=document.title,
                version=document.version,
                source_type=document.source_type,
                content=document.content,
                effective_from=document.effective_from,
                effective_to=document.effective_to,
                applicability=document.applicability,
                status=document.status,
            )
        )
        return KnowledgeIngestionReceiptContract(
            document_id=receipt.document_id,
            content_sha256=receipt.content_sha256,
            chunk_count=receipt.chunk_count,
            duplicate=receipt.duplicate,
        )

    def ingest_upload(
        self,
        metadata: KnowledgeDocumentUploadContract,
        payload: bytes,
        *,
        parser: DocumentParser,
    ) -> KnowledgeIngestionReceiptContract:
        """Parse and index an uploaded document while preserving source citations."""

        sections = tuple(parser.parse(payload, metadata.file_name))
        content = "\n\n".join(section.content for section in sections)
        receipt = self._knowledge_base.ingest(
            KnowledgeDocument(
                document_id=metadata.document_id,
                title=metadata.title,
                version=metadata.version,
                source_type=metadata.source_type,
                content=content,
                effective_from=metadata.effective_from,
                effective_to=metadata.effective_to,
                applicability=metadata.applicability,
                sections=sections,
            )
        )
        return KnowledgeIngestionReceiptContract(
            document_id=receipt.document_id,
            content_sha256=receipt.content_sha256,
            chunk_count=receipt.chunk_count,
            duplicate=receipt.duplicate,
        )

    def supersede(self, document_id: str) -> None:
        """Make a document auditable but unavailable to default retrieval."""

        self._knowledge_base.supersede(document_id)

    def search(
        self,
        query: str,
        *,
        source_types: Sequence[str] = (),
        filters: dict[str, str] | None = None,
        top_k: int = 5,
        effective_at: datetime | None = None,
    ) -> tuple[KnowledgeSearchHitContract, ...]:
        hits = self._knowledge_base.search(
            KnowledgeSearchQuery(
                query=query,
                source_types=tuple(source_types),
                filters=filters or {},
                top_k=top_k,
                effective_at=effective_at,
            )
        )
        return tuple(
            KnowledgeSearchHitContract(
                evidence_id=hit.chunk.evidence_id,
                document_id=hit.chunk.document_id,
                title=hit.chunk.title,
                version=hit.chunk.version,
                source_type=cast(
                    Literal["TECHNICAL_DOCUMENT", "VERIFIED_CASE"], hit.chunk.source_type
                ),
                section=hit.chunk.section,
                page=hit.chunk.page,
                content=hit.chunk.content,
                retrieval_score=hit.score,
                applicability="APPLICABLE",
                applicability_reasons=list(hit.applicability_reasons),
                source_metadata=dict(hit.chunk.applicability),
            )
            for hit in hits
        )
