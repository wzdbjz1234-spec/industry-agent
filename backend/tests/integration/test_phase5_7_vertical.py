"""Phase 5–7 vertical acceptance tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from quality_case_agent.adapters.embeddings.deterministic import DeterministicEmbeddingProvider
from quality_case_agent.adapters.in_memory.approval import InMemoryProposalStore
from quality_case_agent.adapters.in_memory.investigation import (
    InMemoryAnalysisRunStore,
    InMemoryInvestigationEventPublisher,
)
from quality_case_agent.adapters.in_memory.knowledge import InMemoryKnowledgeBase
from quality_case_agent.adapters.in_memory.stores import (
    InMemoryInspectionStore,
    InMemoryMetricsStore,
    InMemoryQualityCaseStore,
)
from quality_case_agent.adapters.knowledge.parsing import MarkdownDocumentParser
from quality_case_agent.adapters.llm.deterministic import DeterministicInvestigationLLM
from quality_case_agent.application.approval.service import ProposalApprovalService
from quality_case_agent.application.case_detection.service import QualityCaseDetectionService
from quality_case_agent.application.ingestion.service import InspectionIngestionService
from quality_case_agent.application.investigation.agent import InvestigationAgent
from quality_case_agent.application.investigation.service import InvestigationService
from quality_case_agent.application.investigation.tools import ReadOnlyInvestigationTools
from quality_case_agent.application.knowledge.service import KnowledgeService
from quality_case_agent.application.metrics.worker import MetricsWorker
from quality_case_agent.contracts.approval import ProposalDecisionContract
from quality_case_agent.contracts.knowledge import (
    KnowledgeDocumentContract,
    KnowledgeDocumentUploadContract,
)
from quality_case_agent.domain.knowledge.models import KnowledgeDocument

from simulator.replay import scenario_replay
from simulator.scenarios import ScenarioName


def _fixture() -> tuple[
    InMemoryInspectionStore,
    InMemoryMetricsStore,
    InMemoryQualityCaseStore,
]:
    inspections = InMemoryInspectionStore()
    metrics = InMemoryMetricsStore()
    cases = InMemoryQualityCaseStore()
    for batch in scenario_replay(ScenarioName.FIXTURE_OFFSET, seed=7, batch_size=10):
        InspectionIngestionService(inspections).submit_batch(batch)
    MetricsWorker(inspections, metrics).run(window_minutes=(1, 5))
    QualityCaseDetectionService(metrics, cases).run()
    return inspections, metrics, cases


def test_upload_requires_applicability_and_keeps_markdown_citations() -> None:
    with pytest.raises(ValidationError):
        KnowledgeDocumentContract(
            document_id="missing-applicability",
            title="Manual",
            version="1.0",
            source_type="TECHNICAL_DOCUMENT",
            content="content",
            effective_from=datetime(2026, 8, 1, tzinfo=UTC),
        )

    base = InMemoryKnowledgeBase(DeterministicEmbeddingProvider())
    service = KnowledgeService(base)
    metadata = KnowledgeDocumentUploadContract(
        document_id="fixture-manual-v4",
        title="Fixture manual",
        version="4.0",
        source_type="TECHNICAL_DOCUMENT",
        file_name="fixture.md",
        content_type="text/markdown",
        effective_from=datetime(2026, 8, 1, tzinfo=UTC),
        applicability={"station_id": "camera-01", "product_id": "part-A"},
    )
    receipt = service.ingest_upload(
        metadata,
        b"# Pin check\n\nMeasure the fixture positioning pin gap.",
        parser=MarkdownDocumentParser(),
    )
    duplicate = service.ingest_upload(
        metadata.model_copy(update={"document_id": "fixture-manual-copy"}),
        b"# Pin check\n\nMeasure the fixture positioning pin gap.",
        parser=MarkdownDocumentParser(),
    )
    assert receipt.chunk_count == 1
    assert duplicate.duplicate
    assert duplicate.document_id == receipt.document_id
    hits = service.search(
        "fixture positioning pin",
        filters={"station_id": "camera-01", "product_id": "part-A"},
    )
    assert hits[0].document_id == "fixture-manual-v4"
    assert hits[0].section == "Pin check"
    assert hits[0].page == 1


def test_case_event_creates_one_analysis_run_and_proposal() -> None:
    inspections, metrics, cases = _fixture()
    knowledge = InMemoryKnowledgeBase()
    knowledge.ingest(
        KnowledgeDocument(
            document_id="manual-v4",
            title="Fixture manual",
            version="4.0",
            source_type="TECHNICAL_DOCUMENT",
            content="Check fixture positioning pin gap and reference part.",
            effective_from=datetime(2026, 8, 1, tzinfo=UTC),
            effective_to=None,
            applicability={"station_id": "camera-01", "product_id": "part-A"},
        )
    )
    tools = ReadOnlyInvestigationTools(cases, metrics, knowledge, inspections)
    runs = InMemoryAnalysisRunStore()
    events = InMemoryInvestigationEventPublisher()
    investigation = InvestigationService(
        InvestigationAgent(DeterministicInvestigationLLM(), tools), runs, events, cases
    )
    proposals = InMemoryProposalStore()
    approval = ProposalApprovalService(proposals, cases, investigation)
    investigation.set_proposal_registrar(approval.register_output)

    event = next(
        event
        for event in cases.events
        if event.event_type == "quality.case.opened.v1"
    )
    first = investigation.handle_case_opened(event)
    replay = investigation.handle_case_opened(event)

    assert first.model_dump(mode="json") == replay.model_dump(mode="json")
    assert len(runs.list_runs()) == 1
    assert len(proposals.list_pending()) == 1
    assert len(proposals.list_proposed_events()) == 1
    assert cases.list_cases()[0].case_status == "AWAITING_APPROVAL"
    assert {item.evidence_class for item in first.analysis.evidence} >= {"A", "B"}
    assert any(item.action == "get_representative_samples" for item in _tool_results(first))


def test_reanalysis_is_new_run_and_approval_is_idempotent() -> None:
    inspections, metrics, cases = _fixture()
    case = cases.list_cases()[0]
    knowledge = InMemoryKnowledgeBase()
    knowledge.ingest(
        KnowledgeDocument(
            document_id="manual-v4",
            title="Fixture manual",
            version="4.0",
            source_type="TECHNICAL_DOCUMENT",
            content="Check fixture positioning pin gap.",
            effective_from=datetime(2026, 8, 1, tzinfo=UTC),
            effective_to=None,
            applicability={"station_id": "camera-01", "product_id": "part-A"},
        )
    )
    runs = InMemoryAnalysisRunStore()
    events = InMemoryInvestigationEventPublisher()
    investigation = InvestigationService(
        InvestigationAgent(
            DeterministicInvestigationLLM(),
            ReadOnlyInvestigationTools(cases, metrics, knowledge, inspections),
        ),
        runs,
        events,
        cases,
    )
    proposals = InMemoryProposalStore()
    approval = ProposalApprovalService(proposals, cases, investigation)
    investigation.set_proposal_registrar(approval.register_output)
    event = next(item for item in cases.events if item.event_type == "quality.case.opened.v1")
    output = investigation.handle_case_opened(event)
    assert output.proposal is not None
    decision = ProposalDecisionContract(
        decision_id="request-reanalysis-1",
        proposal_id=output.proposal.proposal_id,
        case_id=case.case_id,
        decision="REQUEST_REANALYSIS",
        decided_by="engineer-1",
        decided_at=datetime(2026, 8, 23, tzinfo=UTC),
        comment="需要补充现场样本复核",
    )
    first = approval.decide(decision)
    replay = approval.decide(decision)
    assert first.event_id == replay.event_id
    assert first.new_analysis_run_id is not None
    assert len(runs.list_runs()) == 2
    assert cases.list_cases()[0].snapshot.snapshot_id == output.analysis.snapshot_id


def _tool_results(output: object) -> tuple[object, ...]:
    # Trace summaries are the persisted public surface; no model reasoning is exposed.
    trace = output.trace  # type: ignore[attr-defined]
    return tuple(event for event in trace.events if event.event_type == "TOOL_RESULT")
