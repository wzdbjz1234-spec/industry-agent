"""Proposal approval, versioning and idempotency tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from quality_case_agent.adapters.in_memory.approval import InMemoryProposalStore
from quality_case_agent.adapters.in_memory.stores import InMemoryQualityCaseStore
from quality_case_agent.application.approval.service import ProposalApprovalService
from quality_case_agent.contracts.approval import ProposalDecisionContract
from quality_case_agent.contracts.investigation import (
    InvestigationAnalysisContract,
    InvestigationOutputContract,
    ProposalContract,
    ProposalStepContract,
)
from quality_case_agent.domain.quality_case.models import QualityCase, QualityCaseSnapshot


def _setup() -> tuple[ProposalApprovalService, InMemoryProposalStore, InMemoryQualityCaseStore]:
    case_store = InMemoryQualityCaseStore()
    case = QualityCase(
        case_id="case-1",
        fingerprint="case-1",
        trigger_family="FIXTURE_OFFSET",
        opened_at=datetime(2026, 8, 22, tzinfo=UTC),
        snapshot=QualityCaseSnapshot(
            snapshot_id="snapshot-1",
            case_id="case-1",
            created_at=datetime(2026, 8, 22, tzinfo=UTC),
            trigger_family="FIXTURE_OFFSET",
            observations=(),
            lookback_window_minutes=1,
            baseline_ng_rate=0.1,
            baseline_score_mean=0.2,
            data_quality_warnings=(),
        ),
    )
    case_store.save_case(case)
    proposal = ProposalContract(
        proposal_id="proposal-1",
        case_id="case-1",
        analysis_run_id="analysis-1",
        created_at=datetime(2026, 8, 22, tzinfo=UTC),
        title="Check fixture",
        reason="Spatial concentration requires a fixture check.",
        steps=[
            ProposalStepContract(order=1, instruction="Measure pin gap", expected_evidence="Value")
        ],
        requested_role="QUALITY_ENGINEER",
        priority="HIGH",
        risk_level="LOW",
        evidence_ids=["EV-A-1"],
    )
    output = InvestigationOutputContract(
        analysis=InvestigationAnalysisContract(
            analysis_run_id="analysis-1",
            case_id="case-1",
            snapshot_id="snapshot-1",
            status="COMPLETED",
            summary="Actionable analysis.",
            termination_reason="READY",
        ),
        proposal=proposal,
        trace={
            "analysis_run_id": "analysis-1",
            "events": [
                {
                    "sequence": 1,
                    "event_type": "STARTED",
                    "iteration": 0,
                    "action": "start",
                    "summary": "started",
                }
            ],
        },
    )
    proposal_store = InMemoryProposalStore()
    service = ProposalApprovalService(proposal_store, case_store)
    service.register_output(output)
    return service, proposal_store, case_store


def test_reject_and_reanalysis_require_comments() -> None:
    with pytest.raises(ValidationError, match="comment is required"):
        ProposalDecisionContract(
            decision_id="d1",
            proposal_id="p1",
            case_id="c1",
            decision="REJECT",
            decided_by="engineer",
            decided_at=datetime(2026, 8, 22, tzinfo=UTC),
        )
    with pytest.raises(ValidationError, match="comment is required"):
        ProposalDecisionContract(
            decision_id="d2",
            proposal_id="p1",
            case_id="c1",
            decision="REQUEST_REANALYSIS",
            decided_by="engineer",
            decided_at=datetime(2026, 8, 22, tzinfo=UTC),
        )


def test_approve_with_changes_preserves_original_and_is_idempotent() -> None:
    service, proposals, cases = _setup()
    decision = ProposalDecisionContract(
        decision_id="decision-1",
        proposal_id="proposal-1",
        case_id="case-1",
        decision="APPROVE_WITH_CHANGES",
        decided_by="engineer-1",
        decided_at=datetime(2026, 8, 22, 10, 45, tzinfo=UTC),
        comment="Add a light check.",
        approved_steps=["Check light", "Measure pin gap"],
    )
    event = service.decide(decision)
    duplicate = service.decide(decision)

    assert event.event_id == duplicate.event_id
    assert event.approved_proposal_id == "proposal-1:v2"
    assert proposals.get_proposal("proposal-1") is not None
    approved = proposals.get_proposal("proposal-1:v2")
    assert approved is not None
    assert approved.status == "APPROVED"
    assert approved.version == 2
    assert [step.instruction for step in approved.steps] == ["Check light", "Measure pin gap"]
    assert cases.list_cases()[0].case_status == "APPROVED_PENDING_QMS"
    assert len(proposals.list_events()) == 1
