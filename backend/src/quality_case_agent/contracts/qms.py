"""Mock QMS task and signed result contracts."""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel, to_utc
from .investigation import ProposalStepContract


class QmsCreateTaskRequestContract(ContractModel):
    """Transport contract owned by the QMS boundary, not by the Agent."""

    schema_version: Literal["1.0"] = "1.0"
    proposal_id: str = Field(min_length=1, max_length=128)
    case_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    reason: str = Field(min_length=1, max_length=2_000)
    steps: list[ProposalStepContract] = Field(min_length=1, max_length=20)
    assignee_role: str = Field(min_length=1, max_length=128)
    priority: Literal["LOW", "MEDIUM", "HIGH"]
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]


class QmsTaskContract(ContractModel):
    task_id: str = Field(min_length=1, max_length=128)
    case_id: str
    proposal_id: str
    external_system: Literal["MOCK_QMS", "SHADOW_QMS", "SANDBOX_QMS", "PRODUCTION_QMS"] = "MOCK_QMS"
    status: Literal["OPEN", "IN_PROGRESS", "CLOSED"] = "OPEN"
    assignee_role: str = Field(min_length=1, max_length=128)
    created_by: str = Field(min_length=1, max_length=128)
    created_at: datetime
    task_uri: str

    @model_validator(mode="after")
    def normalize_created_at(self) -> "QmsTaskContract":
        object.__setattr__(self, "created_at", to_utc(self.created_at))
        return self


class ActualRootCauseContract(ContractModel):
    code: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=2_000)


class VerificationContract(ContractModel):
    status: Literal["VERIFIED_EFFECTIVE", "NOT_VERIFIED", "INCONCLUSIVE"]
    start: datetime
    end: datetime
    sample_count: int = Field(ge=1)
    ng_rate_before: float = Field(ge=0.0, le=1.0)
    ng_rate_after: float = Field(ge=0.0, le=1.0)
    acceptance_criteria: str = Field(min_length=1, max_length=2_000)
    notes: str = Field(default="", max_length=2_000)

    @model_validator(mode="after")
    def validate_period(self) -> "VerificationContract":
        start = to_utc(self.start)
        end = to_utc(self.end)
        if end <= start:
            raise ValueError("verification end must be after start")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        return self


class AgentAssessmentContract(ContractModel):
    top_hypothesis_matched: bool
    useful: bool
    human_rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2_000)


class QmsTaskResultContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    event_type: Literal["qms.task.result-submitted.v1"] = "qms.task.result-submitted.v1"
    event_id: str = Field(min_length=1, max_length=128)
    occurred_at: datetime
    confirmation_id: str = Field(min_length=1, max_length=128)
    case_id: str
    task_id: str
    confirmed_by: str = Field(min_length=1, max_length=128)
    actual_root_cause: ActualRootCauseContract
    actual_actions: list[str] = Field(min_length=1, max_length=20)
    verification: VerificationContract
    agent_assessment: AgentAssessmentContract

    @model_validator(mode="after")
    def normalize_occurred_at(self) -> "QmsTaskResultContract":
        object.__setattr__(self, "occurred_at", to_utc(self.occurred_at))
        return self


class QmsTaskCreatedEventContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    event_id: str
    event_type: Literal["qms.task.created.v1"] = "qms.task.created.v1"
    occurred_at: datetime
    task: QmsTaskContract

    @model_validator(mode="after")
    def normalize_occurred_at(self) -> "QmsTaskCreatedEventContract":
        object.__setattr__(self, "occurred_at", to_utc(self.occurred_at))
        return self


class CaseConfirmedEventContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    event_id: str
    event_type: Literal["quality.case.confirmed.v1"] = "quality.case.confirmed.v1"
    occurred_at: datetime
    case_id: str
    confirmation_id: str
    verification_status: Literal["VERIFIED_EFFECTIVE", "NOT_VERIFIED", "INCONCLUSIVE"]
    knowledge_promotion_eligible: bool
    confirmed_by: str

    @model_validator(mode="after")
    def normalize_occurred_at(self) -> "CaseConfirmedEventContract":
        object.__setattr__(self, "occurred_at", to_utc(self.occurred_at))
        return self
