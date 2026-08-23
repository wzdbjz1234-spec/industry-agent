"""In-memory Proposal version and approval event store."""

from collections.abc import Sequence

from quality_case_agent.contracts.approval import ApprovalEventContract, ProposalDecisionContract
from quality_case_agent.contracts.investigation import (
    InvestigationOutputContract,
    InvestigationProposedEventContract,
    ProposalContract,
)


class InMemoryProposalStore:
    def __init__(self) -> None:
        self._proposals: dict[str, ProposalContract] = {}
        self._outputs: dict[str, InvestigationOutputContract] = {}
        self._decisions: dict[str, ProposalDecisionContract] = {}
        self._events: dict[str, ApprovalEventContract] = {}
        self._proposed_events: dict[str, InvestigationProposedEventContract] = {}

    def save_output(self, output: InvestigationOutputContract) -> ProposalContract:
        if output.proposal is None:
            raise ValueError("an investigation output without a Proposal cannot be approved")
        proposal = output.proposal
        existing_output = self._outputs.get(output.analysis.analysis_run_id)
        if existing_output is not None and existing_output.model_dump(mode="json") != output.model_dump(mode="json"):
            raise ValueError("analysis output is immutable")
        existing_proposal = self._proposals.get(proposal.proposal_id)
        if existing_proposal is not None and existing_proposal != proposal:
            raise ValueError("proposal_id already contains different payload")
        self._outputs.setdefault(output.analysis.analysis_run_id, output)
        self._proposals.setdefault(proposal.proposal_id, proposal)
        return self._proposals[proposal.proposal_id]

    def get_proposal(self, proposal_id: str) -> ProposalContract | None:
        return self._proposals.get(proposal_id)

    def save_proposal(self, proposal: ProposalContract) -> None:
        self._proposals[proposal.proposal_id] = proposal

    def get_decision(self, decision_id: str) -> ProposalDecisionContract | None:
        return self._decisions.get(decision_id)

    def save_decision(self, decision: ProposalDecisionContract) -> None:
        existing = self._decisions.get(decision.decision_id)
        if existing is not None and existing != decision:
            raise ValueError("decision_id already contains different payload")
        self._decisions[decision.decision_id] = decision

    def save_event(self, event: ApprovalEventContract) -> None:
        existing = self._events.get(event.event_id)
        if existing is not None and existing != event:
            raise ValueError("approval event ID already contains different payload")
        self._events.setdefault(event.event_id, event)

    def save_proposed_event(self, event: InvestigationProposedEventContract) -> None:
        existing = self._proposed_events.get(event.event_id)
        if existing is not None and existing != event:
            raise ValueError(f"proposal event already contains different payload: {event.event_id}")
        self._proposed_events.setdefault(event.event_id, event)

    def list_events(self) -> Sequence[ApprovalEventContract]:
        return tuple(sorted(self._events.values(), key=lambda event: event.occurred_at))

    def list_pending(self) -> Sequence[ProposalContract]:
        return tuple(
            sorted(
                (proposal for proposal in self._proposals.values() if proposal.status == "PENDING_APPROVAL"),
                key=lambda proposal: (proposal.created_at, proposal.proposal_id),
            )
        )

    def list_decisions(self) -> Sequence[ProposalDecisionContract]:
        return tuple(sorted(self._decisions.values(), key=lambda decision: decision.decided_at))

    def list_proposed_events(self) -> Sequence[InvestigationProposedEventContract]:
        return tuple(sorted(self._proposed_events.values(), key=lambda event: event.occurred_at))

    @property
    def proposal_count(self) -> int:
        return len(self._proposals)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)
