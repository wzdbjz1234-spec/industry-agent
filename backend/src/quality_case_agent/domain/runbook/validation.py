"""Convert strict Runbook contracts into executable-free domain objects."""

from quality_case_agent.contracts.runbook import RunbookContract
from quality_case_agent.domain.runbook.models import (
    Runbook,
    RunbookHypothesis,
    RunbookProposal,
    RunbookStep,
)


def to_domain(contract: RunbookContract) -> Runbook:
    proposal = None
    if contract.proposal is not None:
        proposal = RunbookProposal(
            title=contract.proposal.title,
            reason=contract.proposal.reason,
            steps=tuple(
                RunbookStep(
                    order=step.order,
                    instruction=step.instruction,
                    expected_evidence=step.expected_evidence,
                )
                for step in contract.proposal.steps
            ),
            requested_role=contract.proposal.requested_role,
            priority=contract.proposal.priority,
            risk_level=contract.proposal.risk_level,
        )
    return Runbook(
        runbook_id=contract.runbook_id,
        version=contract.version,
        trigger_family=contract.trigger_family,
        required_tools=tuple(contract.required_tools),
        knowledge_query=contract.knowledge_query,
        candidate_hypotheses=tuple(
            RunbookHypothesis(
                hypothesis_id=item.hypothesis_id,
                title=item.title,
                description=item.description,
                default_confidence=item.default_confidence,
                missing_evidence=tuple(item.missing_evidence),
            )
            for item in contract.candidate_hypotheses
        ),
        proposal=proposal,
    )
