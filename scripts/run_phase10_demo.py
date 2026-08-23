"""Run the Phase 10 historical-case reuse demo end to end."""

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
from quality_case_agent.entrypoints.api.app import ApplicationContainer, build_demo_container

from simulator.replay import scenario_replay
from simulator.scenarios import ScenarioName


def _open_new_cases(
    container: ApplicationContainer,
    *,
    start_at: datetime | None = None,
    replay_id: str | None = None,
) -> tuple[str, ...]:
    for batch in scenario_replay(
        ScenarioName.FIXTURE_OFFSET,
        seed=7,
        batch_size=10,
        start_at=start_at,
        replay_id=replay_id,
    ):
        InspectionIngestionService(container.inspection).submit_batch(batch)
    MetricsWorker(container.inspection, container.metrics).run(window_minutes=(1, 5))
    detection = QualityCaseDetectionService(container.metrics, container.cases).run()
    for event in detection.events:
        if event.event_type == "quality.case.opened.v1":
            container.investigations.handle_case_opened(event)
    return tuple(case.case_id for case in container.cases.list_cases())


def _close_case(container: ApplicationContainer, case_id: str, suffix: str) -> None:
    proposal = next(item for item in container.proposals.list_pending() if item.case_id == case_id)
    approved = container.approval.decide(
        ProposalDecisionContract(
            decision_id=f"decision-phase10-{suffix}",
            proposal_id=proposal.proposal_id,
            case_id=case_id,
            decision="APPROVE",
            decided_by="engineer-phase10",
            decided_at=datetime.now(UTC),
        )
    )
    task_event = container.qms_worker.handle(approved)
    if task_event is None:
        raise RuntimeError("Phase 10 demo did not create a QMS task")
    now = datetime.now(UTC)
    result = QmsTaskResultContract(
        event_id=f"qms-result-phase10-{suffix}",
        occurred_at=now,
        confirmation_id=f"confirmation-phase10-{suffix}",
        case_id=case_id,
        task_id=task_event.task.task_id,
        confirmed_by="engineer-phase10",
        actual_root_cause=ActualRootCauseContract(
            code="FIXTURE_LOCATING_PIN_LOOSE",
            description="定位销松动导致工件向右上方向偏移",
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
        ),
        agent_assessment=AgentAssessmentContract(
            top_hypothesis_matched=True,
            useful=True,
            human_rating=4,
            comment="历史案例帮助缩短了排查范围，但现场结果仍独立验证。",
        ),
    )
    container.closure.process(result, sign_qms_result(result, b"phase9-demo-secret"))


def main() -> int:
    container = build_demo_container()
    first_ids = _open_new_cases(container)
    if not first_ids:
        raise RuntimeError("Phase 10 demo did not open the first Case")
    _close_case(container, first_ids[0], "first")

    all_ids = _open_new_cases(
        container,
        start_at=datetime(2026, 8, 23, 2, 0, tzinfo=UTC),
        replay_id="repeat-01",
    )
    second_id = next(case_id for case_id in all_ids if case_id != first_ids[0])
    second_case = container.cases.get_case(second_id)
    if second_case is None or second_case.proposal_id is None:
        raise RuntimeError("Phase 10 demo did not create the second Proposal")
    proposal = container.proposals.get_proposal(second_case.proposal_id)
    if proposal is None:
        raise RuntimeError("Phase 10 demo Proposal disappeared")
    output = container.runs.get_output(proposal.analysis_run_id)
    if output is None:
        raise RuntimeError("Phase 10 demo Analysis output disappeared")

    historical = [item for item in output.analysis.evidence if item.evidence_class == "C"]
    print(
        json.dumps(
            {
                "first_case_id": first_ids[0],
                "second_case_id": second_id,
                "trusted_case_count": len(container.verified_case_index.list_records()),
                "historical_evidence": [
                    {
                        "evidence_id": item.evidence_id,
                        "reference": item.reference,
                        "applicability": item.applicability,
                        "claim": item.claim,
                    }
                    for item in historical
                ],
                "proposal_reason": proposal.reason,
                "limitations": output.analysis.limitations,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
