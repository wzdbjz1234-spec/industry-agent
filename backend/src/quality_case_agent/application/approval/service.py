"""Human Proposal approval use case."""

from uuid import NAMESPACE_URL, uuid5

from quality_case_agent.application.audit.service import AuditService
from quality_case_agent.application.identity.policy import system_identity
from quality_case_agent.application.ports.approval import ProposalStore
from quality_case_agent.application.ports.investigation import ReanalysisRequester
from quality_case_agent.application.ports.quality_case import QualityCaseStore
from quality_case_agent.contracts.approval import ApprovalEventContract, ProposalDecisionContract
from quality_case_agent.contracts.investigation import (
    InvestigationOutputContract,
    InvestigationProposedEventContract,
    ProposalContract,
    ProposalStepContract,
)


class ProposalApprovalService:
    """Apply human decisions while retaining original and approved Proposal versions."""

    def __init__(
        self,
        proposals: ProposalStore,
        cases: QualityCaseStore,
        reanalysis: ReanalysisRequester | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self._proposals = proposals
        self._cases = cases
        self._reanalysis = reanalysis
        self._audit = audit

    def register_output(self, output: InvestigationOutputContract) -> ProposalContract:
        proposal = self._proposals.save_output(output)
        case = self._cases.get_case(proposal.case_id)
        if case is None:
            raise KeyError(f"case not found: {proposal.case_id}")
        case.mark_awaiting_approval(proposal.proposal_id)
        self._cases.save_case(case)
        self._proposals.save_proposed_event(
            InvestigationProposedEventContract(
                event_id=f"{proposal.proposal_id}:proposed",
                occurred_at=proposal.created_at,
                proposal=proposal,
                analysis_run_id=proposal.analysis_run_id,
                case_id=proposal.case_id,
            )
        )
        if self._audit is not None:
            self._audit.record(
                system_identity("system:investigation-agent", role="QUALITY_ENGINEER", organization="agent"),
                event_type="quality.proposal.created.audit.v1",
                action="CREATE",
                resource_type="proposal",
                resource_id=proposal.proposal_id,
                correlation_id=proposal.analysis_run_id,
                trace_id=proposal.analysis_run_id,
                metadata={"case_id": proposal.case_id, "version": proposal.version},
            )
        return proposal

    def decide(self, decision: ProposalDecisionContract) -> ApprovalEventContract:
        previous = self._proposals.get_decision(decision.decision_id)
        if previous is not None:
            if previous != decision:
                raise ValueError("decision_id already contains a different decision")
            try:
                return next(
                    event
                    for event in self._proposals.list_events()
                    if event.decision_id == decision.decision_id
                )
            except StopIteration as exc:
                raise RuntimeError("decision exists without its approval event") from exc

        proposal = self._proposals.get_proposal(decision.proposal_id)
        if proposal is None:
            raise KeyError(f"proposal not found: {decision.proposal_id}")
        if proposal.case_id != decision.case_id:
            raise ValueError("decision case_id does not match Proposal")
        case = self._cases.get_case(decision.case_id)
        if case is None:
            raise KeyError(f"case not found: {decision.case_id}")

        event_type: str
        approved_proposal_id: str | None = None
        new_analysis_run_id: str | None = None
        if decision.decision in {"APPROVE", "APPROVE_WITH_CHANGES"}:
            approved = self._approved_version(proposal, decision)
            if decision.decision == "APPROVE_WITH_CHANGES":
                self._proposals.save_proposal(proposal.model_copy(update={"status": "SUPERSEDED"}))
            self._proposals.save_proposal(approved)
            approved_proposal_id = approved.proposal_id
            event_type = "quality.investigation.approved.v1"
        elif decision.decision == "REJECT":
            event_type = "quality.investigation.rejected.v1"
            self._proposals.save_proposal(proposal.model_copy(update={"status": "REJECTED"}))
            case.case_status = "WAITING_INVESTIGATION"
        else:
            event_type = "quality.investigation.reanalysis.requested.v1"
            new_analysis_run_id = self._reanalysis_run_id(decision)
            if self._reanalysis is not None:
                new_analysis_run_id = self._reanalysis.reanalyze(
                    case.case_id,
                    case.snapshot.snapshot_id,
                    decision.decision_id,
                )
            case.mark_analyzing()

        if decision.decision in {"APPROVE", "APPROVE_WITH_CHANGES"}:
            case.mark_approved_pending_qms(approved_proposal_id or proposal.proposal_id)
        self._cases.save_case(case)

        event = ApprovalEventContract(
            event_id=f"evt-{decision.decision_id}",
            event_type=event_type,  # type: ignore[arg-type]
            occurred_at=decision.decided_at,
            decision_id=decision.decision_id,
            proposal_id=proposal.proposal_id,
            case_id=proposal.case_id,
            decided_by=decision.decided_by,
            decision=decision,
            approved_proposal_id=approved_proposal_id,
            new_analysis_run_id=new_analysis_run_id,
        )
        self._proposals.save_decision(decision)
        self._proposals.save_event(event)
        return event

    @staticmethod
    def _approved_version(
        proposal: ProposalContract, decision: ProposalDecisionContract
    ) -> ProposalContract:
        if decision.decision == "APPROVE":
            return proposal.model_copy(update={"status": "APPROVED"})
        original_id = proposal.original_proposal_id or proposal.proposal_id
        version = proposal.version + 1
        steps = [
            ProposalStepContract(
                order=index, instruction=step, expected_evidence="人工审批指定证据"
            )
            for index, step in enumerate(decision.approved_steps, start=1)
        ]
        return proposal.model_copy(
            update={
                "proposal_id": f"{original_id}:v{version}",
                "original_proposal_id": original_id,
                "version": version,
                "steps": steps,
                "status": "APPROVED",
            }
        )

    @staticmethod
    def _reanalysis_run_id(decision: ProposalDecisionContract) -> str:
        value = uuid5(NAMESPACE_URL, f"reanalysis:{decision.decision_id}")
        return f"ar-rerun-{value.hex[:16]}"
