"""Ports for Proposal versioning and human decisions."""

from collections.abc import Sequence
from typing import Protocol

from quality_case_agent.contracts.approval import ApprovalEventContract, ProposalDecisionContract
from quality_case_agent.contracts.investigation import (
    InvestigationOutputContract,
    InvestigationProposedEventContract,
    ProposalContract,
)


class ProposalStore(Protocol):
    def save_output(self, output: InvestigationOutputContract) -> ProposalContract:
        """Persist an analysis output and its original Proposal."""

    def get_proposal(self, proposal_id: str) -> ProposalContract | None:
        """Return any stored Proposal version by ID."""

    def save_proposal(self, proposal: ProposalContract) -> None:
        """Persist a new Proposal version."""

    def get_decision(self, decision_id: str) -> ProposalDecisionContract | None:
        """Return a prior decision for idempotent replay."""

    def save_decision(self, decision: ProposalDecisionContract) -> None:
        """Persist a decision command."""

    def save_event(self, event: ApprovalEventContract) -> None:
        """Persist an approval event idempotently."""

    def save_proposed_event(self, event: InvestigationProposedEventContract) -> None:
        """Persist the proposal-created event idempotently."""

    def list_events(self) -> Sequence[ApprovalEventContract]:
        """Return approval events in decision order."""

    def list_pending(self) -> Sequence[ProposalContract]:
        """Return current proposal versions waiting for human review."""

    def list_decisions(self) -> Sequence[ProposalDecisionContract]:
        """Return decision commands for audit views."""
