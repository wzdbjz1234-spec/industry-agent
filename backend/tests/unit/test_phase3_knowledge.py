"""Offline knowledge ingestion and retrieval tests."""

from datetime import UTC, datetime

from quality_case_agent.adapters.in_memory.knowledge import InMemoryKnowledgeBase
from quality_case_agent.domain.knowledge.models import KnowledgeDocument, KnowledgeSearchQuery


def _document(document_id: str, version: str, status: str = "ACTIVE") -> KnowledgeDocument:
    return KnowledgeDocument(
        document_id=document_id,
        title="Fixture maintenance manual",
        version=version,
        source_type="TECHNICAL_DOCUMENT",
        content="# Pin inspection\n\nCheck fixture positioning pin gap and verify with a reference part.",
        effective_from=datetime(2026, 8, 1, tzinfo=UTC),
        effective_to=None,
        applicability={"station_id": "camera-01", "product_id": "part-A"},
        status=status,
    )


def test_hash_idempotency_and_metadata_filtered_search() -> None:
    base = InMemoryKnowledgeBase()
    first = base.ingest(_document("doc-v3", "3.2"))
    duplicate = base.ingest(_document("doc-v3-copy", "3.2"))

    assert first.chunk_count == 2
    assert not first.duplicate
    assert duplicate.duplicate
    hits = base.search(
        KnowledgeSearchQuery(
            query="fixture positioning pin inspection",
            source_types=("TECHNICAL_DOCUMENT",),
            filters={"station_id": "camera-01", "product_id": "part-A"},
            effective_at=datetime(2026, 8, 23, tzinfo=UTC),
        )
    )
    assert hits
    assert hits[0].chunk.document_id == "doc-v3"
    assert hits[0].chunk.page is not None
    assert hits[0].applicability_reasons


def test_superseded_document_is_excluded_from_default_results() -> None:
    base = InMemoryKnowledgeBase()
    base.ingest(_document("doc-v3", "3.2"))
    base.supersede("doc-v3")
    hits = base.search(
        KnowledgeSearchQuery(
            query="fixture positioning pin inspection",
            source_types=("TECHNICAL_DOCUMENT",),
            filters={"station_id": "camera-01"},
            effective_at=datetime(2026, 8, 23, tzinfo=UTC),
        )
    )
    assert hits == ()
