"""Phase 20 evidence grounding and historical-case safety tests."""

from quality_case_agent.application.investigation.grounding import EvidenceGroundingValidator
from quality_case_agent.contracts.investigation import (
    EvidenceContract,
    HypothesisContract,
    InvestigationAnalysisContract,
    ProposalContract,
    ProposalStepContract,
)


def _analysis() -> InvestigationAnalysisContract:
    return InvestigationAnalysisContract(
        analysis_run_id="ar-grounding",
        case_id="case-1",
        snapshot_id="snapshot-1",
        status="COMPLETED",
        summary="summary",
        evidence=[
            EvidenceContract(
                evidence_id="EV-A-001",
                evidence_class="A",
                evidence_type="CURRENT_SNAPSHOT",
                reference="snapshot-1#/observations",
                claim="current fact",
                applicability="DIRECT",
            ),
            EvidenceContract(
                evidence_id="EV-B-001",
                evidence_class="B",
                evidence_type="TECHNICAL_DOCUMENT",
                reference="manual-v1#1",
                claim="applicable procedure",
                applicability="APPLICABLE",
            ),
            EvidenceContract(
                evidence_id="EV-C-001",
                evidence_class="C",
                evidence_type="VERIFIED_CASE",
                reference="archive://case-previous",
                claim="historical experience",
                applicability="CONTEXTUAL",
            ),
        ],
        hypotheses=[
            HypothesisContract(
                hypothesis_id="H-1",
                title="candidate",
                description="candidate",
                confidence=0.5,
                supporting_evidence_ids=["EV-A-001"],
            )
        ],
        termination_reason="done",
    )


def _proposal(evidence_ids: list[str]) -> ProposalContract:
    return ProposalContract(
        proposal_id="prop-1",
        case_id="case-1",
        analysis_run_id="ar-grounding",
        created_at="2026-08-25T00:00:00Z",
        title="proposal",
        reason="reason",
        steps=[ProposalStepContract(order=1, instruction="inspect", expected_evidence="reading")],
        requested_role="QUALITY_ENGINEER",
        priority="HIGH",
        risk_level="LOW",
        evidence_ids=evidence_ids,
    )


def test_grounding_accepts_current_and_applicable_evidence() -> None:
    result = EvidenceGroundingValidator().validate(_analysis(), _proposal(["EV-A-001", "EV-B-001"]))
    assert result.valid
    assert result.supported_evidence_ids == ("EV-A-001",)


def test_grounding_rejects_unknown_and_historical_support() -> None:
    validator = EvidenceGroundingValidator()
    analysis = _analysis().model_copy(
        update={
            "hypotheses": [
                _analysis().hypotheses[0].model_copy(
                    update={"supporting_evidence_ids": ["EV-C-001", "EV-UNKNOWN"]}
                )
            ]
        }
    )
    result = validator.validate(analysis, _proposal(["EV-C-001", "EV-UNKNOWN"]))
    assert not result.valid
    assert any("historical C evidence" in error for error in result.errors)
    assert any("unknown evidence" in error for error in result.errors)
