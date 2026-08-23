"""Replaceable enterprise knowledge-base port."""

from collections.abc import Sequence
from typing import Protocol

from quality_case_agent.domain.knowledge.models import (
    DocumentSection,
    KnowledgeDocument,
    KnowledgeIngestionReceipt,
    KnowledgeSearchHit,
    KnowledgeSearchQuery,
)


class KnowledgeBase(Protocol):
    def ingest(self, document: KnowledgeDocument) -> KnowledgeIngestionReceipt:
        """Index a document with content-hash idempotency."""

    def search(self, query: KnowledgeSearchQuery) -> Sequence[KnowledgeSearchHit]:
        """Search only active, applicable chunks."""

    def supersede(self, document_id: str) -> None:
        """Mark an old version unavailable to default retrieval."""


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> tuple[float, ...]:
        """Provider-neutral seam for a future embedding implementation."""


class DocumentParser(Protocol):
    def parse(self, payload: bytes, file_name: str) -> Sequence[DocumentSection]:
        """Parse an uploaded file into citation-preserving sections."""
