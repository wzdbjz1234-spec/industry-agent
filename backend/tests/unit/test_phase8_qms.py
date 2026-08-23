"""Phase 8 QMS adapter and consumer-worker tests."""

from datetime import UTC, datetime

import httpx
from quality_case_agent.adapters.in_memory.approval import InMemoryProposalStore
from quality_case_agent.adapters.in_memory.qms import InMemoryQmsDeliveryStore
from quality_case_agent.adapters.in_memory.stores import InMemoryQualityCaseStore
from quality_case_agent.adapters.qms.http import HttpQmsClient
from quality_case_agent.adapters.qms.mock import MockQmsAdapter
from quality_case_agent.application.ports.qms import QmsPermanentError
from quality_case_agent.application.qms.service import QmsIntegrationService
from quality_case_agent.application.qms.worker import QmsIntegrationWorker
from quality_case_agent.contracts.approval import ApprovalEventContract, ProposalDecisionContract
from quality_case_agent.contracts.investigation import ProposalContract, ProposalStepContract
from quality_case_agent.contracts.qms import QmsTaskContract
from quality_case_agent.domain.quality_case.metrics import QualityMetricWindow
from quality_case_agent.domain.quality_case.models import QualityCase, QualityCaseSnapshot


def _fixture() -> tuple[
    InMemoryProposalStore,
    InMemoryQualityCaseStore,
    ProposalContract,
    ApprovalEventContract,
]:
    now = datetime(2026, 8, 23, 10, 0, tzinfo=UTC)
    window = QualityMetricWindow(
        window_start=now,
        window_minutes=5,
        factory_id="factory-1",
        line_id="line-1",
        station_id="camera-01",
        product_id="part-A",
        total_count=100,
        ng_count=9,
        ng_rate=0.09,
        score_mean=0.4,
        score_p95=0.8,
        region_counts=(("upper_right", 9),),
        model_versions=("efficientad-v1",),
        warnings=(),
    )
    case_id = "case-phase8-001"
    snapshot = QualityCaseSnapshot(
        snapshot_id="snapshot-phase8-001",
        case_id=case_id,
        created_at=now,
        trigger_family="FIXTURE_OFFSET",
        observations=(window,),
        lookback_window_minutes=30,
        baseline_ng_rate=0.01,
        baseline_score_mean=0.1,
        data_quality_warnings=(),
    )
    cases = InMemoryQualityCaseStore()
    cases.save_case(
        QualityCase(
            case_id=case_id,
            fingerprint="fingerprint-phase8-001",
            trigger_family="FIXTURE_OFFSET",
            opened_at=now,
            snapshot=snapshot,
        )
    )
    proposal = ProposalContract(
        proposal_id="proposal-phase8-001",
        case_id=case_id,
        analysis_run_id="run-phase8-001",
        created_at=now,
        title="检查夹具定位销",
        reason="右上区域异常集中，需要现场确认定位销间隙。",
        steps=[
            ProposalStepContract(
                order=1,
                instruction="测量定位销间隙",
                expected_evidence="测量记录和参考件对比照片",
            )
        ],
        requested_role="QUALITY_ENGINEER",
        priority="HIGH",
        risk_level="MEDIUM",
        status="APPROVED",
    )
    proposals = InMemoryProposalStore()
    proposals.save_proposal(proposal)
    decision = ProposalDecisionContract(
        decision_id="decision-phase8-001",
        proposal_id=proposal.proposal_id,
        case_id=case_id,
        decision="APPROVE",
        decided_by="engineer-1",
        decided_at=now,
    )
    event = ApprovalEventContract(
        event_id="evt-phase8-approved-001",
        event_type="quality.investigation.approved.v1",
        occurred_at=now,
        decision_id=decision.decision_id,
        proposal_id=proposal.proposal_id,
        case_id=case_id,
        decided_by=decision.decided_by,
        decision=decision,
        approved_proposal_id=proposal.proposal_id,
    )
    return proposals, cases, proposal, event


def test_worker_retries_transient_qms_and_replays_processed_event() -> None:
    proposals, cases, _, event = _fixture()
    qms = MockQmsAdapter(clock=lambda: datetime(2026, 8, 23, 10, 0, 2, tzinfo=UTC))
    worker = QmsIntegrationWorker(
        QmsIntegrationService(proposals, cases, qms),
        InMemoryQmsDeliveryStore(),
    )
    qms.fail_next(2)

    assert worker.handle(event) is None
    assert worker.pending()[0].attempts == 1
    assert worker.handle(event) is None
    assert worker.pending()[0].attempts == 2

    result = worker.retry_pending()[0]
    assert result.task.task_id == "QMS-TASK-0001"
    assert worker.handle(event) == result
    assert qms.task_count == 1
    assert cases.list_cases()[0].qms_task_uri == "http://localhost:8001/tasks/QMS-TASK-0001"
    assert cases.list_cases()[0].case_status == "QMS_OPEN"


def test_worker_sends_permanent_and_exhausted_failures_to_dlq() -> None:
    proposals, cases, _, event = _fixture()
    qms = MockQmsAdapter()
    worker = QmsIntegrationWorker(
        QmsIntegrationService(proposals, cases, qms),
        InMemoryQmsDeliveryStore(),
        max_attempts=2,
    )
    rejected = event.model_copy(
        update={
            "event_id": "evt-phase8-rejected-001",
            "event_type": "quality.investigation.rejected.v1",
        }
    )
    assert worker.handle(rejected) is None
    assert len(worker.dlq()) == 1
    assert qms.task_count == 0

    qms.set_available(False)
    assert worker.handle(event) is None
    assert worker.handle(event) is None
    assert len(worker.dlq()) == 2
    assert worker.dlq()[-1].attempts == 2


def test_http_qms_client_maps_contracts_and_not_found() -> None:
    task = QmsTaskContract(
        task_id="QMS-TASK-0001",
        case_id="case-phase8-001",
        proposal_id="proposal:phase8:001",
        created_at=datetime(2026, 8, 23, 10, 0, 2, tzinfo=UTC),
        assignee_role="QUALITY_ENGINEER",
        created_by="quality-integration-service",
        task_uri="http://qms/tasks/QMS-TASK-0001",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.raw_path.decode()
        if path.endswith("/by-proposal/proposal%3Aphase8%3A001"):
            return httpx.Response(200, json=task.model_dump(mode="json"), request=request)
        if path.endswith("/by-proposal/proposal%3Amissing"):
            return httpx.Response(404, json={"detail": "not found"}, request=request)
        if request.method == "GET" and request.url.path == "/api/v1/tasks":
            return httpx.Response(200, json={"items": [task.model_dump(mode="json")]}, request=request)
        return httpx.Response(201, json=task.model_dump(mode="json"), request=request)

    client = HttpQmsClient(
        "http://qms",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    proposals, _, proposal, _ = _fixture()
    proposal = proposal.model_copy(update={"proposal_id": task.proposal_id})
    proposals.save_proposal(proposal)
    assert client.create_task(proposal).task_id == task.task_id
    assert client.get_task_by_proposal(task.proposal_id) == task
    assert client.get_task_by_proposal("proposal:missing") is None
    assert client.list_tasks() == (task,)

    def bad_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"detail": "bad request"}, request=request)

    bad_client = HttpQmsClient(
        "http://qms",
        client=httpx.Client(transport=httpx.MockTransport(bad_handler)),
    )
    try:
        bad_client.list_tasks()
    except QmsPermanentError:
        pass
    else:
        raise AssertionError("expected QMS 400 to map to QmsPermanentError")
