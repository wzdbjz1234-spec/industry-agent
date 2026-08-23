"""Human approval commands and versioned approval events."""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel, to_utc


class ProposalDecisionContract(ContractModel):
    decision_id: str = Field(min_length=1, max_length=128)
    proposal_id: str = Field(min_length=1, max_length=128)
    case_id: str = Field(min_length=1, max_length=128)
    decision: Literal["APPROVE", "APPROVE_WITH_CHANGES", "REJECT", "REQUEST_REANALYSIS"]
    decided_by: str = Field(min_length=1, max_length=128)
    decided_at: datetime
    comment: str = Field(default="", max_length=2_000)
    approved_steps: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_decision_requirements(self) -> "ProposalDecisionContract":
        if self.decision == "REJECT" and not self.comment.strip():
            raise ValueError("comment is required when rejecting a Proposal")
        if self.decision == "APPROVE_WITH_CHANGES" and not self.approved_steps:
            raise ValueError("approved_steps is required when approving with changes")
        if self.decision == "REQUEST_REANALYSIS" and not self.comment.strip():
            raise ValueError("comment is required when requesting reanalysis")
        object.__setattr__(self, "decided_at", to_utc(self.decided_at))
        return self


class ApprovalEventContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    event_id: str = Field(min_length=1, max_length=128)
    event_type: Literal[
        "quality.investigation.approved.v1",
        "quality.investigation.rejected.v1",
        "quality.investigation.reanalysis.requested.v1",
    ]
    occurred_at: datetime
    decision_id: str
    proposal_id: str
    case_id: str
    decided_by: str
    decision: ProposalDecisionContract
    approved_proposal_id: str | None = None
    new_analysis_run_id: str | None = None

    @model_validator(mode="after")
    def normalize_occurred_at(self) -> "ApprovalEventContract":
        object.__setattr__(self, "occurred_at", to_utc(self.occurred_at))
        return self
