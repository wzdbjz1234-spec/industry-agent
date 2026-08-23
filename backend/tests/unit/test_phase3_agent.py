"""Deterministic bounded Agent unit tests."""

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
from quality_case_agent.application.investigation.agent import AgentLimits, InvestigationAgent
from quality_case_agent.application.investigation.tools import ReadOnlyInvestigationTools
from quality_case_agent.application.metrics.worker import MetricsWorker
from quality_case_agent.domain.knowledge.models import KnowledgeDocument

from simulator.replay import scenario_replay
from simulator.scenarios import ScenarioName


def _fixture_case() -> tuple[InMemoryQualityCaseStore, InMemoryMetricsStore]:
    inspections = InMemoryInspectionStore()
    metrics = InMemoryMetricsStore()
    cases = InMemoryQualityCaseStore()
    ingestion = InspectionIngestionService(inspections)
    for batch in scenario_replay(ScenarioName.FIXTURE_OFFSET, seed=7, batch_size=10):
        ingestion.submit_batch(batch)
    MetricsWorker(inspections, metrics).run(window_minutes=(1, 5))
    QualityCaseDetectionService(metrics, cases).run()
    return cases, metrics


def _knowledge() -> InMemoryKnowledgeBase:
    base = InMemoryKnowledgeBase()
    base.ingest(
        KnowledgeDocument(
            document_id="manual-v3",
            title="Fixture manual",
            version="3.2",
            source_type="TECHNICAL_DOCUMENT",
            content="Fixture positioning pin inspection and reference part verification.",
            effective_from=datetime(2026, 8, 1, tzinfo=UTC),
            effective_to=None,
            applicability={"station_id": "camera-01", "product_id": "part-A"},
        )
    )
    base.ingest(
        KnowledgeDocument(
            document_id="history-1",
            title="Verified fixture case",
            version="1.0",
            source_type="VERIFIED_CASE",
            content="Verified positioning pin issue caused upper right offset and recovered after replacement.",
            effective_from=datetime(2026, 8, 1, tzinfo=UTC),
            effective_to=None,
            applicability={"station_id": "camera-01", "product_id": "part-A"},
        )
    )
    return base


def test_agent_uses_only_allowlisted_tools_and_is_deterministic() -> None:
    cases, metrics = _fixture_case()
    case = cases.list_cases()[0]
    tools = ReadOnlyInvestigationTools(cases, metrics, _knowledge())
    agent = InvestigationAgent(DeterministicInvestigationLLM(), tools)
    first = agent.analyze(case.case_id, case.snapshot.snapshot_id)
    second = agent.analyze(case.case_id, case.snapshot.snapshot_id)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.analysis.status == "COMPLETED"
    assert first.proposal is not None
    assert {event.action for event in first.trace.events} <= {
        "investigation_started",
        "get_case_snapshot",
        "compare_quality_metrics",
        "search_knowledge_base",
        "submit_investigation_analysis",
    }
    assert all(event.event_type != "TERMINATED" for event in first.trace.events)


def test_agent_stops_at_iteration_budget_without_writes() -> None:
    cases, metrics = _fixture_case()
    case = cases.list_cases()[0]
    tools = ReadOnlyInvestigationTools(cases, metrics, _knowledge())
    result = InvestigationAgent(
        DeterministicInvestigationLLM(), tools, AgentLimits(max_iterations=1)
    ).analyze(case.case_id, case.snapshot.snapshot_id)

    assert result.analysis.status == "BUDGET_EXHAUSTED"
    assert result.proposal is None
