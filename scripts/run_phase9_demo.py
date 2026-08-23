"""Run the Phase 9 signed QMS result and knowledge-closure demo."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from quality_case_agent.application.case_detection.service import QualityCaseDetectionService
from quality_case_agent.application.ingestion.service import InspectionIngestionService
from quality_case_agent.application.metrics.worker import MetricsWorker
from quality_case_agent.application.qms.service import sign_qms_result
from quality_case_agent.contracts.approval import ProposalDecisionContract
from quality_case_agent.contracts.qms import (
    ActualRootCauseContract,
    AgentAssessmentContract,
    QmsTaskResultContract,
    VerificationContract,
)
from quality_case_agent.entrypoints.api.app import build_demo_container

from simulator.replay import scenario_replay
from simulator.scenarios import ScenarioName


def main() -> int:
    container = build_demo_container()
    for batch in scenario_replay(ScenarioName.FIXTURE_OFFSET, seed=7, batch_size=10):
        InspectionIngestionService(container.inspection).submit_batch(batch)
    MetricsWorker(container.inspection, container.metrics).run(window_minutes=(1, 5))
    detection = QualityCaseDetectionService(container.metrics, container.cases).run()
    for event in detection.events:
        if event.event_type == "quality.case.opened.v1":
            container.investigations.handle_case_opened(event)

    proposal = container.proposals.list_pending()[0]
    decision = ProposalDecisionContract(
        decision_id="decision-phase9-demo-001",
        proposal_id=proposal.proposal_id,
        case_id=proposal.case_id,
        decision="APPROVE",
        decided_by="engineer-phase9",
        decided_at=datetime.now(UTC),
    )
    approved = container.approval.decide(decision)
    task_event = container.qms_worker.handle(approved)
    if task_event is None:
        raise RuntimeError("Phase 9 demo did not create a QMS task")

    now = datetime.now(UTC)
    result = QmsTaskResultContract(
        event_id="qms-result-phase9-demo-001",
        occurred_at=now,
        confirmation_id="confirmation-phase9-demo-001",
        case_id=proposal.case_id,
        task_id=task_event.task.task_id,
        confirmed_by="engineer-phase9",
        actual_root_cause=ActualRootCauseContract(
            code="FIXTURE_LOCATING_PIN_LOOSE", description="定位销松动导致工件向右上方向偏移"
        ),
        actual_actions=["更换定位销", "重新标定夹具"],
        verification=VerificationContract(
            status="VERIFIED_EFFECTIVE",
            start=now - timedelta(hours=1),
            end=now,
            sample_count=500,
            ng_rate_before=0.087,
            ng_rate_after=0.018,
            acceptance_criteria="连续500件NG率低于2%",
            notes="异常空间聚集消失",
        ),
        agent_assessment=AgentAssessmentContract(
            top_hypothesis_matched=True,
            useful=True,
            human_rating=4,
            comment="排查步骤有效",
        ),
    )
    signature = sign_qms_result(result, b"phase9-demo-secret")
    first = container.closure.process(result, signature)
    replay = container.closure.process(result, signature)
    case = container.cases.get_case(proposal.case_id)
    if case is None:
        raise RuntimeError("Phase 9 demo Case disappeared")

    print(
        json.dumps(
            {
                "case_id": case.case_id,
                "case_status": case.case_status,
                "archive_uri": first.archived.archive_uri,
                "archive_revision": case.archive_revision,
                "archive_event_idempotent": first.archived == replay.archived,
                "knowledge_index_status": first.archived.knowledge_index_status,
                "trusted_case_count": len(container.verified_case_index.list_records()),
                "content_hash": first.archived.content_hash,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
