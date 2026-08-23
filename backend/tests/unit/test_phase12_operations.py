"""Phase 12 operations projections and controlled DLQ recovery."""

from datetime import UTC, datetime

from quality_case_agent.adapters.in_memory.qms import InMemoryQmsDeliveryStore
from quality_case_agent.application.observability.service import (
    CaseEventTimelineProjection,
    WorkerMetricsRegistry,
)
from quality_case_agent.application.ports.qms import QmsTransientError
from quality_case_agent.application.qms.worker import QmsIntegrationWorker
from quality_case_agent.contracts.approval import ApprovalEventContract, ProposalDecisionContract
from quality_case_agent.contracts.qms import QmsTaskContract, QmsTaskCreatedEventContract


def _approval_event() -> ApprovalEventContract:
    decision = ProposalDecisionContract(
        decision_id="decision-phase12-001",
        proposal_id="prop-phase12-001",
        case_id="qc-phase12-001",
        decision="APPROVE",
        decided_by="operator",
        decided_at=datetime(2026, 8, 23, 12, 0, tzinfo=UTC),
    )
    return ApprovalEventContract(
        event_id="evt-phase12-approval-001",
        event_type="quality.investigation.approved.v1",
        occurred_at=decision.decided_at,
        decision_id=decision.decision_id,
        proposal_id=decision.proposal_id,
        case_id=decision.case_id,
        decided_by=decision.decided_by,
        decision=decision,
        approved_proposal_id=decision.proposal_id,
    )


class _FlakyQmsService:
    def __init__(self) -> None:
        self.failures_left = 2

    def handle_approved(self, event: ApprovalEventContract) -> QmsTaskCreatedEventContract:
        if self.failures_left:
            self.failures_left -= 1
            raise QmsTransientError("knowledge timeout token=secret https://internal/qms")
        task = QmsTaskContract(
            task_id="QMS-PHASE12-001",
            case_id=event.case_id,
            proposal_id=event.proposal_id,
            assignee_role="QUALITY_ENGINEER",
            created_by="quality-case-agent",
            created_at=datetime(2026, 8, 23, 12, 1, tzinfo=UTC),
            task_uri="mock://qms/tasks/QMS-PHASE12-001",
        )
        return QmsTaskCreatedEventContract(
            event_id="evt-qms-phase12-001",
            occurred_at=task.created_at,
            task=task,
        )


def test_dlq_retry_preserves_event_and_records_authorized_audit() -> None:
    event = _approval_event()
    metrics = WorkerMetricsRegistry()
    worker = QmsIntegrationWorker(
        _FlakyQmsService(),
        InMemoryQmsDeliveryStore(),
        max_attempts=2,
        metrics=metrics,
    )

    assert worker.handle(event) is None
    assert worker.handle(event) is None
    dlq = worker.dlq()[0]
    assert dlq.state == "DLQ"
    assert dlq.event.event_id == event.event_id
    assert "REDACTED" in (dlq.last_error or "")
    assert "internal" not in (dlq.last_error or "")

    result = worker.retry_dlq(event.event_id, operator_id="human-operator")
    assert result is not None
    assert worker.pending() == ()
    assert worker.dlq() == ()
    assert worker.processed()[0].event.event_id == event.event_id
    audit = worker.retry_audit()[0]
    assert audit.previous_state == "DLQ"
    assert audit.resulting_state == "PROCESSED"
    assert audit.operator_id == "human-operator"
    assert metrics.snapshot()[0]["error_count"] == 2


def test_timeline_projection_is_idempotent_and_filters_by_case() -> None:
    projection = CaseEventTimelineProjection()
    event = _approval_event()
    first = projection.record(event, source="approval-store")
    second = projection.record(event, source="duplicate-source")
    assert first == second
    assert len(projection.list(case_id=event.case_id)) == 1
    assert projection.list(trace_id="missing") == ()
