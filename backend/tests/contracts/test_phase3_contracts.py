"""Contract tests for Phase 3 knowledge and investigation outputs."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from quality_case_agent.contracts.investigation import (
    AgentTraceEventContract,
    EvidenceContract,
    InvestigationAnalysisContract,
    InvestigationOutputContract,
    InvestigationTraceContract,
)
from quality_case_agent.contracts.knowledge import KnowledgeDocumentContract


def test_knowledge_document_requires_timezone_and_metadata() -> None:
    document = KnowledgeDocumentContract(
        document_id="doc-1",
        title="Fixture manual",
        version="3.2",
        source_type="TECHNICAL_DOCUMENT",
        content="check fixture pin",
        effective_from=datetime(2026, 8, 1, tzinfo=UTC),
        applicability={"station_id": "camera-01"},
    )
    assert document.effective_from.tzinfo is not None
    with pytest.raises(ValidationError, match="timestamps must include a timezone"):
        KnowledgeDocumentContract(
            document_id="doc-2",
            title="Bad manual",
            version="1",
            source_type="TECHNICAL_DOCUMENT",
            content="content",
            effective_from=datetime(2026, 8, 1),  # noqa: DTZ001 - intentional invalid contract input
        )


def test_investigation_output_is_json_serializable() -> None:
    evidence = EvidenceContract(
        evidence_id="EV-A-001",
        evidence_class="A",
        evidence_type="CURRENT_SNAPSHOT",
        reference="snapshot-1#/observations",
        claim="NG rate increased",
        supports=["H-01"],
        applicability="DIRECT",
    )
    analysis = InvestigationAnalysisContract(
        analysis_run_id="ar-1",
        case_id="case-1",
        snapshot_id="snapshot-1",
        status="INSUFFICIENT_EVIDENCE",
        summary="Need more data",
        evidence=[evidence],
        termination_reason="insufficient evidence",
    )
    trace = InvestigationTraceContract(
        analysis_run_id="ar-1",
        events=[
            AgentTraceEventContract(
                sequence=1,
                event_type="STARTED",
                iteration=0,
                action="investigation_started",
                summary="started",
            )
        ],
    )
    output = InvestigationOutputContract(analysis=analysis, trace=trace)
    encoded = output.model_dump_json()
    assert InvestigationOutputContract.model_validate_json(encoded) == output
