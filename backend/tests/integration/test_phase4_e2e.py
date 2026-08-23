"""Offline human approval -> Mock QMS -> archive/index integration tests."""

from datetime import UTC, datetime

import pytest
from quality_case_agent.adapters.in_memory.approval import InMemoryProposalStore
from quality_case_agent.adapters.in_memory.archive import (
    InMemoryCaseArchiveStore,
    InMemoryVerifiedCaseIndex,
)
from quality_case_agent.adapters.in_memory.knowledge import InMemoryKnowledgeBase
from quality_case_agent.adapters.in_memory.stores import (
    InMemoryInspectionStore,
    InMemoryMetricsStore,
    InMemoryQualityCaseStore,
)
from quality_case_agent.adapters.llm.deterministic import DeterministicInvestigationLLM
from quality_case_agent.adapters.qms.mock import MockQmsAdapter
from quality_case_agent.application.approval.service import ProposalApprovalService
from quality_case_agent.application.archival.service import CaseArchiveService
from quality_case_agent.application.case_detection.service import QualityCaseDetectionService
from quality_case_agent.application.ingestion.service import InspectionIngestionService
from quality_case_agent.application.investigation.agent import InvestigationAgent
from quality_case_agent.application.investigation.tools import ReadOnlyInvestigationTools
from quality_case_agent.application.metrics.worker import MetricsWorker
from quality_case_agent.application.qms.service import QmsIntegrationService, QmsWebhookService
from quality_case_agent.contracts.approval import ProposalDecisionContract
from quality_case_agent.contracts.knowledge import KnowledgeDocumentContract
from quality_case_agent.contracts.qms import (
    ActualRootCauseContract,
    AgentAssessmentContract,
    QmsTaskResultContract,
    VerificationContract,
)

from simulator.replay import scenario_replay
from simulator.scenarios import ScenarioName


def test_human_loop_is_idempotent_and_promotes_only_verified_cases() -> None:
    inspection = InMemoryInspectionStore()
    metrics = InMemoryMetricsStore()
    cases = InMemoryQualityCaseStore()
    for batch in scenario_replay(ScenarioName.FIXTURE_OFFSET, seed=7, batch_size=10):
        InspectionIngestionService(inspection).submit_batch(batch)
    MetricsWorker(inspection, metrics).run(window_minutes=(1, 5))
    detection = QualityCaseDetectionService(metrics, cases).run()
    case = detection.opened_cases[0]

    knowledge = InMemoryKnowledgeBase()
    knowledge.ingest(
        KnowledgeDocumentContract(
            document_id="manual",
            title="Fixture manual",
            version="3.2",
            source_type="TECHNICAL_DOCUMENT",
            content="# Pin check\n\nCheck fixture positioning pin gap.",
            effective_from=datetime(2026, 8, 1, tzinfo=UTC),
            applicability={"station_id": "camera-01", "product_id": "part-A"},
        )
    )
    investigation = InvestigationAgent(
        DeterministicInvestigationLLM(), ReadOnlyInvestigationTools(cases, metrics, knowledge)
    ).analyze(case.case_id, case.snapshot.snapshot_id)

    proposals = InMemoryProposalStore()
    approval = ProposalApprovalService(proposals, cases)
    original = approval.register_output(investigation)
    decision = ProposalDecisionContract(
        decision_id="decision-e2e-1",
        proposal_id=original.proposal_id,
        case_id=case.case_id,
        decision="APPROVE",
        decided_by="engineer-1",
        decided_at=datetime(2026, 8, 22, 10, 45, tzinfo=UTC),
    )
    approved = approval.decide(decision)
    qms = MockQmsAdapter(clock=lambda: datetime(2026, 8, 22, 10, 45, 2, tzinfo=UTC))
    qms_service = QmsIntegrationService(proposals, cases, qms)
    with pytest.raises(ValueError, match="only approved events"):
        qms_service.handle_approved(
            approved.model_copy(update={"event_type": "quality.investigation.rejected.v1"})
        )
    task_event = qms_service.handle_approved(approved)
    qms_service.handle_approved(approved)
    assert qms.task_count == 1

    result = QmsTaskResultContract(
        event_id="qms-result-e2e-1",
        occurred_at=datetime(2026, 8, 22, 13, 20, tzinfo=UTC),
        confirmation_id="confirmation-e2e-1",
        case_id=case.case_id,
        task_id=task_event.task.task_id,
        confirmed_by="engineer-1",
        actual_root_cause=ActualRootCauseContract(
            code="FIXTURE_LOCATING_PIN_LOOSE", description="定位销松动导致右上偏移"
        ),
        actual_actions=["更换定位销", "重新标定夹具"],
        verification=VerificationContract(
            status="VERIFIED_EFFECTIVE",
            start=datetime(2026, 8, 22, 12, 30, tzinfo=UTC),
            end=datetime(2026, 8, 22, 13, 15, tzinfo=UTC),
            sample_count=500,
            ng_rate_before=0.087,
            ng_rate_after=0.018,
            acceptance_criteria="连续500件NG率低于2%",
        ),
        agent_assessment=AgentAssessmentContract(
            top_hypothesis_matched=True, useful=True, human_rating=4
        ),
    )
    webhook = QmsWebhookService(cases, b"secret")
    signature = webhook.sign(result)
    confirmed = webhook.process(result, signature)
    assert webhook.process(result, signature).event_id == confirmed.event_id
    with pytest.raises(ValueError, match="invalid QMS webhook signature"):
        webhook.process(result, "bad-signature")
    assert cases.list_cases()[0].case_status == "CONFIRMED"

    archive_store = InMemoryCaseArchiveStore()
    index = InMemoryVerifiedCaseIndex()
    archive = CaseArchiveService(archive_store, index)
    archived = archive.archive(case, investigation, original.proposal_id, task_event.task, result)
    assert (
        archive.archive(case, investigation, original.proposal_id, task_event.task, result).event_id
        == archived.event_id
    )
    assert archive_store.object_count == 1
    assert len(index.list_records()) == 1
    assert index.list_records()[0].metadata["date_prefix"] == "2026-08-22"
    assert cases.list_cases()[0].case_status == "ARCHIVED"
