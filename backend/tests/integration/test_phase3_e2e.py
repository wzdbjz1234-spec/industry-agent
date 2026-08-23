"""End-to-end offline Case -> tools -> knowledge -> proposal test."""

from datetime import UTC, datetime

from quality_case_agent.adapters.in_memory.knowledge import InMemoryKnowledgeBase
from quality_case_agent.adapters.in_memory.stores import (
    InMemoryInspectionStore,
    InMemoryMetricsStore,
    InMemoryQualityCaseStore,
)
from quality_case_agent.adapters.llm.deterministic import DeterministicInvestigationLLM
from quality_case_agent.application.case_detection.service import QualityCaseDetectionService
from quality_case_agent.application.ingestion.service import InspectionIngestionService
from quality_case_agent.application.investigation.agent import InvestigationAgent
from quality_case_agent.application.investigation.tools import ReadOnlyInvestigationTools
from quality_case_agent.application.metrics.worker import MetricsWorker
from quality_case_agent.domain.knowledge.models import KnowledgeDocument

from simulator.replay import scenario_replay
from simulator.scenarios import ScenarioName


def test_fixture_offset_case_produces_evidence_backed_proposal() -> None:
    inspection = InMemoryInspectionStore()
    metrics = InMemoryMetricsStore()
    cases = InMemoryQualityCaseStore()
    ingestion = InspectionIngestionService(inspection)
    for batch in scenario_replay(ScenarioName.FIXTURE_OFFSET, seed=7, batch_size=10):
        ingestion.submit_batch(batch)
    MetricsWorker(inspection, metrics).run(window_minutes=(1, 5))
    detection = QualityCaseDetectionService(metrics, cases).run()
    case = detection.opened_cases[0]

    kb = InMemoryKnowledgeBase()
    common = {
        "station_id": "camera-01",
        "product_id": "part-A",
    }
    for document_id, source_type, content in (
        (
            "manual-v3",
            "TECHNICAL_DOCUMENT",
            "Check fixture positioning pin gap and reference part.",
        ),
        (
            "history-1",
            "VERIFIED_CASE",
            "Verified positioning pin offset recovered after pin replacement.",
        ),
    ):
        kb.ingest(
            KnowledgeDocument(
                document_id=document_id,
                title=document_id,
                version="1.0",
                source_type=source_type,
                content=content,
                effective_from=datetime(2026, 8, 1, tzinfo=UTC),
                effective_to=None,
                applicability=common,
            )
        )

    result = InvestigationAgent(
        DeterministicInvestigationLLM(), ReadOnlyInvestigationTools(cases, metrics, kb)
    ).analyze(case.case_id, case.snapshot.snapshot_id)
    classes = {item.evidence_class for item in result.analysis.evidence}

    assert result.analysis.status == "COMPLETED"
    assert {"A", "B", "C"} <= classes
    assert result.proposal is not None
    assert result.proposal.status == "PENDING_APPROVAL"
    assert [event.action for event in result.trace.events][-1] == "submit_investigation_analysis"
