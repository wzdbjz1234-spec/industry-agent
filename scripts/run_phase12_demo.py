"""Run the Phase 12 DLQ, controlled retry and operations projection demo."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime

from quality_case_agent.application.case_detection.service import QualityCaseDetectionService
from quality_case_agent.application.ingestion.service import InspectionIngestionService
from quality_case_agent.application.metrics.worker import MetricsWorker
from quality_case_agent.application.observability.service import CaseEventTimelineProjection
from quality_case_agent.application.ports.qms import QmsTransientError
from quality_case_agent.application.qms.service import QmsIntegrationService
from quality_case_agent.application.qms.worker import QmsIntegrationWorker
from quality_case_agent.contracts.approval import ProposalDecisionContract
from quality_case_agent.entrypoints.api.app import build_demo_container

from simulator.replay import scenario_replay
from simulator.scenarios import ScenarioName


class _TimeoutThenRecover:
    """Simulate a bounded external timeout before handing off to the real QMS service."""

    def __init__(self, delegate: QmsIntegrationService) -> None:
        self._delegate = delegate
        self._failures_left = 2

    def handle_approved(self, event):
        if self._failures_left:
            self._failures_left -= 1
            raise QmsTransientError("knowledge retrieval timeout token=secret")
        return self._delegate.handle_approved(event)


def main() -> int:
    container = build_demo_container()
    for batch in scenario_replay(ScenarioName.FIXTURE_OFFSET, seed=7, batch_size=10):
        InspectionIngestionService(container.inspection).submit_batch(batch)
    MetricsWorker(container.inspection, container.metrics).run(window_minutes=(1, 5))
    detection = QualityCaseDetectionService(container.metrics, container.cases).run()
    for event in detection.events:
        if event.event_type == "quality.case.opened.v1":
            container.investigations.handle_case_opened(event)
    case = container.cases.list_cases()[0]
    proposal = container.proposals.list_pending()[0]
    approval = container.approval.decide(
        ProposalDecisionContract(
            decision_id="decision-phase12-demo",
            proposal_id=proposal.proposal_id,
            case_id=case.case_id,
            decision="APPROVE",
            decided_by="phase12-human-operator",
            decided_at=datetime.now(UTC),
        )
    )

    worker = QmsIntegrationWorker(
        _TimeoutThenRecover(
            QmsIntegrationService(container.proposals, container.cases, container.qms)
        ),
        container.qms_delivery,
        max_attempts=2,
        metrics=container.worker_metrics,
    )
    container.qms_worker = worker
    worker.handle(approval)
    worker.handle(approval)
    dlq = replace(worker.dlq()[0])
    worker.retry_dlq(approval.event_id, operator_id="phase12-human-operator")
    processed = worker.processed()[0]
    timeline = CaseEventTimelineProjection()
    for event in container.cases.events:
        timeline.record(event, source="case-store")
    for event in container.events.list_events():
        timeline.record(event, source="investigation-worker")
    timeline.record(approval, source="approval-store")
    timeline.record_delivery(dlq)
    timeline.record_delivery(processed)
    if processed.result is not None:
        timeline.record(processed.result, source="qms-integration-worker")
    run = container.runs.list_runs()[0]
    print(
        json.dumps(
            {
                "case_id": case.case_id,
                "analysis_status": run.status,
                "original_event_id": approval.event_id,
                "dlq": {
                    "state": dlq.state,
                    "attempts": dlq.attempts,
                    "error_type": dlq.last_error_type,
                    "error": dlq.last_error,
                },
                "recovered": {
                    "state": processed.state,
                    "attempts": processed.attempts,
                    "task_id": processed.result.task.task_id if processed.result else None,
                },
                "retry_audit": [item.as_dict() for item in worker.retry_audit()],
                "timeline": [item.as_dict() for item in timeline.list(case_id=case.case_id)],
                "worker_metrics": container.worker_metrics.snapshot(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
