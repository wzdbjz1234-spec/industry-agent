"""Run the Phase 8 approval -> QMS Worker -> Mock QMS demo."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from quality_case_agent.application.case_detection.service import QualityCaseDetectionService
from quality_case_agent.application.ingestion.service import InspectionIngestionService
from quality_case_agent.application.metrics.worker import MetricsWorker
from quality_case_agent.contracts.approval import ProposalDecisionContract
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
        decision_id="decision-phase8-demo-001",
        proposal_id=proposal.proposal_id,
        case_id=proposal.case_id,
        decision="APPROVE",
        decided_by="engineer-phase8",
        decided_at=datetime(2026, 8, 23, 10, 0, tzinfo=UTC),
    )
    approval_event = container.approval.decide(decision)
    first = container.qms_worker.handle(approval_event)
    replay = container.qms_worker.handle(approval_event)
    case = container.cases.get_case(proposal.case_id)
    if first is None or case is None:
        raise RuntimeError("Phase 8 demo did not create a QMS task")

    print(
        json.dumps(
            {
                "case_id": case.case_id,
                "case_status": case.case_status,
                "qms_task_id": case.qms_task_id,
                "qms_task_uri": case.qms_task_uri,
                "qms_task_count": container.qms.task_count,
                "duplicate_event_replayed": replay == first,
                "delivery_state": container.qms_delivery.get(
                    approval_event.event_id, "qms-integration-worker"
                ).state,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
