"""Phase 10 trusted historical-case retrieval and evidence-boundary tests."""

from datetime import UTC, datetime

from quality_case_agent.adapters.in_memory.knowledge import InMemoryKnowledgeBase
from quality_case_agent.domain.knowledge.models import KnowledgeDocument, KnowledgeSearchQuery


def _case_document(
    document_id: str,
    *,
    product_id: str = "part-A",
    verification_status: str = "VERIFIED_EFFECTIVE",
    date_prefix: str = "2026-08-22",
) -> KnowledgeDocument:
    return KnowledgeDocument(
        document_id=document_id,
        title="已验证历史案例",
        version="archive-r1",
        source_type="VERIFIED_CASE",
        content="定位销松动导致右上偏移，替换后验证有效。",
        effective_from=datetime(1970, 1, 1, tzinfo=UTC),
        effective_to=None,
        applicability={
            "case_id": document_id,
            "case_status": "CONFIRMED",
            "verification_status": verification_status,
            "station_id": "camera-01",
            "product_id": product_id,
            "trigger_family": "FIXTURE_OFFSET",
            "date_prefix": date_prefix,
            "archive_uri": f"case_archive/{document_id}.json",
        },
    )


def test_verified_case_search_filters_trust_and_case_metadata() -> None:
    knowledge = InMemoryKnowledgeBase()
    knowledge.ingest(_case_document("case-good"))
    knowledge.ingest(_case_document("case-wrong-product", product_id="part-B"))
    knowledge.ingest(_case_document("case-not-verified", verification_status="NOT_VERIFIED"))

    query = KnowledgeSearchQuery(
        query="定位销 右上 偏移",
        source_types=("VERIFIED_CASE",),
        filters={
            "station_id": "camera-01",
            "product_id": "part-A",
            "trigger_family": "FIXTURE_OFFSET",
            "date_prefix": "2026-08-22",
        },
        effective_at=datetime(2026, 8, 23, tzinfo=UTC),
    )
    hits = knowledge.search(query)

    assert [hit.chunk.document_id for hit in hits] == ["case-good"]
    assert hits[0].chunk.applicability["archive_uri"] == "case_archive/case-good.json"


def test_wrong_date_metadata_does_not_match_a_verified_case() -> None:
    knowledge = InMemoryKnowledgeBase()
    knowledge.ingest(_case_document("case-good"))

    hits = knowledge.search(
        KnowledgeSearchQuery(
            query="定位销 偏移",
            source_types=("VERIFIED_CASE",),
            filters={"station_id": "camera-01", "product_id": "part-A", "date_prefix": "2026-08-23"},
        )
    )

    assert hits == ()
