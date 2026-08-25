"""Phase 21 transport and identity contract invariants."""

from datetime import UTC, datetime
import httpx
import pytest
from pydantic import ValidationError
from quality_case_agent.contracts.identity import AuditEventContract, IdentityContract
from quality_case_agent.contracts.qms import QmsTaskContract
from quality_case_agent.adapters.qms.http import HttpQmsClient
from quality_case_agent.contracts.investigation import ProposalContract, ProposalStepContract


def test_identity_contract_requires_a_valid_expiration_window() -> None:
    with pytest.raises(ValidationError):
        IdentityContract(
            actor_id="user-1",
            subject="sub-1",
            roles=["VIEWER"],
            organization="plant-a",
            auth_source="OIDC",
            claims_digest="a" * 64,
            issued_at=datetime(2026, 1, 1, tzinfo=UTC),
            expires_at=datetime(2025, 1, 1, tzinfo=UTC),
        )


def test_qms_task_accepts_shadow_system_marker_and_audit_contract_is_strict() -> None:
    task = QmsTaskContract(
        task_id="shadow-1",
        case_id="case-1",
        proposal_id="proposal-1",
        external_system="SHADOW_QMS",
        assignee_role="QUALITY_ENGINEER",
        created_by="shadow",
        created_at=datetime(2026, 8, 25, tzinfo=UTC),
        task_uri="shadow://qms/tasks/shadow-1",
    )
    assert task.external_system == "SHADOW_QMS"
    with pytest.raises(ValidationError):
        AuditEventContract.model_validate({"event_id": "audit-1", "event_type": "x"})


def test_http_qms_adapter_sends_idempotency_key() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["idempotency"] = request.headers["Idempotency-Key"]
        return httpx.Response(
            200,
            json={
                "task_id": "sandbox-task-1",
                "case_id": "case-1",
                "proposal_id": "proposal-1",
                "external_system": "SANDBOX_QMS",
                "assignee_role": "QUALITY_ENGINEER",
                "created_by": "qms",
                "created_at": "2026-08-25T00:00:00Z",
                "task_uri": "https://qms/tasks/sandbox-task-1",
            },
        )

    proposal = ProposalContract(
        proposal_id="proposal-1",
        case_id="case-1",
        analysis_run_id="run-1",
        created_at="2026-08-25T00:00:00Z",
        title="title",
        reason="reason",
        steps=[ProposalStepContract(order=1, instruction="inspect", expected_evidence="reading")],
        requested_role="QUALITY_ENGINEER",
        priority="LOW",
        risk_level="LOW",
        status="APPROVED",
    )
    client = HttpQmsClient(
        "https://qms.example",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    client.create_task(proposal)
    assert captured["idempotency"] == "proposal-1"
