"""Phase 21 Shadow QMS has deterministic idempotency and no external write."""

from datetime import UTC, datetime

import pytest
from quality_case_agent.application.qms.modes import ShadowQmsAdapter
from quality_case_agent.contracts.investigation import ProposalContract, ProposalStepContract


def _proposal(status: str = "APPROVED") -> ProposalContract:
    return ProposalContract(
        proposal_id="proposal-shadow-1",
        case_id="case-shadow-1",
        analysis_run_id="run-shadow-1",
        created_at=datetime(2026, 8, 25, tzinfo=UTC),
        title="shadow proposal",
        reason="validate payload mapping",
        steps=[ProposalStepContract(order=1, instruction="inspect", expected_evidence="reading")],
        requested_role="QUALITY_ENGINEER",
        priority="LOW",
        risk_level="LOW",
        status=status,  # type: ignore[arg-type]
    )


def test_shadow_adapter_is_idempotent_and_does_not_need_a_network() -> None:
    adapter = ShadowQmsAdapter()
    first = adapter.create_task(_proposal())
    second = adapter.create_task(_proposal())
    assert first == second
    assert first.external_system == "SHADOW_QMS"
    assert first.task_uri.startswith("shadow://")
    assert len(adapter.list_tasks()) == 1
    with pytest.raises(ValueError):
        adapter.create_task(_proposal("PENDING_APPROVAL"))
