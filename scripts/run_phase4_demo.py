"""Run the offline Phase 4 human approval/QMS/archive demo."""

from __future__ import annotations

import json
from datetime import UTC, datetime

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


def main() -> int:
    inspection = InMemoryInspectionStore()
    metrics = InMemoryMetricsStore()
    cases = InMemoryQualityCaseStore()
    ingestion = InspectionIngestionService(inspection)
    for batch in scenario_replay(ScenarioName.FIXTURE_OFFSET, seed=7, batch_size=10):
        ingestion.submit_batch(batch)
    MetricsWorker(inspection, metrics).run(window_minutes=(1, 5))
    detection = QualityCaseDetectionService(metrics, cases).run()
    case = detection.opened_cases[0]

    knowledge = InMemoryKnowledgeBase()
    effective_from = datetime(2026, 8, 1, tzinfo=UTC)
    for document_id, source_type, content in (
        (
            "doc-fixture-manual-v3",
            "TECHNICAL_DOCUMENT",
            "# 4.1 定位销检查\n\n检查定位销间隙并使用基准件复测位置。",
        ),
        (
            "case-fixture-verified-001",
            "VERIFIED_CASE",
            "定位销松动导致右上偏移，更换定位销后NG率恢复。",
        ),
    ):
        knowledge.ingest(
            KnowledgeDocumentContract(
                document_id=document_id,
                title=document_id,
                version="1.0",
                source_type=source_type,
                content=content,
                effective_from=effective_from,
                applicability={"station_id": "camera-01", "product_id": "part-A"},
            )
        )
    analysis = InvestigationAgent(
        DeterministicInvestigationLLM(), ReadOnlyInvestigationTools(cases, metrics, knowledge)
    ).analyze(case.case_id, case.snapshot.snapshot_id)

    proposals = InMemoryProposalStore()
    approval = ProposalApprovalService(proposals, cases)
    original = approval.register_output(analysis)
    decision = ProposalDecisionContract(
        decision_id="decision-phase4-001",
        proposal_id=original.proposal_id,
        case_id=case.case_id,
        decision="APPROVE_WITH_CHANGES",
        decided_by="engineer-01",
        decided_at=datetime(2026, 8, 22, 10, 45, tzinfo=UTC),
        comment="增加光源检查并调整任务顺序",
        approved_steps=["检查光源角度和亮度", "测量定位销间隙", "使用基准件复测工件位置"],
    )
    approved_event = approval.decide(decision)
    duplicate_approved_event = approval.decide(decision)

    qms = MockQmsAdapter(clock=lambda: datetime(2026, 8, 22, 10, 45, 2, tzinfo=UTC))
    qms_service = QmsIntegrationService(proposals, cases, qms)
    task_event = qms_service.handle_approved(approved_event)
    qms_service.handle_approved(approved_event)

    result = QmsTaskResultContract(
        event_id="qms-result-phase4-001",
        occurred_at=datetime(2026, 8, 22, 13, 20, tzinfo=UTC),
        confirmation_id="confirmation-phase4-001",
        case_id=case.case_id,
        task_id=task_event.task.task_id,
        confirmed_by="engineer-01",
        actual_root_cause=ActualRootCauseContract(
            code="FIXTURE_LOCATING_PIN_LOOSE", description="定位销松动导致工件向右上方向偏移"
        ),
        actual_actions=["更换定位销", "重新标定夹具", "使用基准件完成位置确认"],
        verification=VerificationContract(
            status="VERIFIED_EFFECTIVE",
            start=datetime(2026, 8, 22, 12, 30, tzinfo=UTC),
            end=datetime(2026, 8, 22, 13, 15, tzinfo=UTC),
            sample_count=500,
            ng_rate_before=0.0871,
            ng_rate_after=0.018,
            acceptance_criteria="连续500件NG率低于2%",
            notes="异常空间聚集消失",
        ),
        agent_assessment=AgentAssessmentContract(
            top_hypothesis_matched=True, useful=True, human_rating=4, comment="排查顺序有效"
        ),
    )
    webhook = QmsWebhookService(cases, b"phase4-demo-secret")
    signature = webhook.sign(result)
    confirmed_event = webhook.process(result, signature)
    duplicate_confirmed_event = webhook.process(result, signature)

    archive_store = InMemoryCaseArchiveStore()
    verified_index = InMemoryVerifiedCaseIndex()
    archive = CaseArchiveService(archive_store, verified_index)
    archive_event = archive.archive(
        case,
        analysis,
        approved_event.approved_proposal_id or original.proposal_id,
        task_event.task,
        result,
    )
    duplicate_archive_event = archive.archive(
        case,
        analysis,
        approved_event.approved_proposal_id or original.proposal_id,
        task_event.task,
        result,
    )
    print(
        json.dumps(
            {
                "case_id": case.case_id,
                "original_proposal_id": original.proposal_id,
                "approved_proposal_id": approved_event.approved_proposal_id,
                "approval_event_idempotent": approved_event.event_id
                == duplicate_approved_event.event_id,
                "qms_task_id": task_event.task.task_id,
                "qms_task_count": qms.task_count,
                "confirmation_event_idempotent": confirmed_event.event_id
                == duplicate_confirmed_event.event_id,
                "archive_uri": archive_event.archive_uri,
                "archive_event_idempotent": archive_event.event_id
                == duplicate_archive_event.event_id,
                "archive_object_count": archive_store.object_count,
                "verified_index_count": len(verified_index.list_records()),
                "case_status": case.case_status,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
