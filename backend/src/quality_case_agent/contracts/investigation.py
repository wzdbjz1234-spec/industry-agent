"""Structured investigation analysis, evidence, proposal and trace contracts."""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel, to_utc


class EvidenceContract(ContractModel):
    evidence_id: str = Field(min_length=1, max_length=128)
    evidence_class: Literal["A", "B", "C"]
    evidence_type: str = Field(min_length=1, max_length=128)
    reference: str = Field(min_length=1, max_length=512)
    claim: str = Field(min_length=1, max_length=2_000)
    supports: list[str] = Field(default_factory=list)
    contradicts: list[str] = Field(default_factory=list)
    applicability: Literal["DIRECT", "APPLICABLE", "CONTEXTUAL", "NOT_APPLICABLE"]
    retrieved_at: datetime | None = None


class HypothesisContract(ContractModel):
    hypothesis_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=2_000)
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


class ProposalStepContract(ContractModel):
    order: int = Field(ge=1)
    instruction: str = Field(min_length=1, max_length=1_000)
    expected_evidence: str = Field(min_length=1, max_length=1_000)


class ProposalContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    proposal_id: str = Field(min_length=1, max_length=128)
    original_proposal_id: str | None = None
    version: int = Field(default=1, ge=1)
    case_id: str
    analysis_run_id: str
    created_at: datetime
    title: str = Field(min_length=1, max_length=256)
    reason: str = Field(min_length=1, max_length=2_000)
    steps: list[ProposalStepContract] = Field(min_length=1, max_length=20)
    requested_role: str = Field(min_length=1, max_length=128)
    priority: Literal["LOW", "MEDIUM", "HIGH"]
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    evidence_ids: list[str] = Field(default_factory=list)
    status: Literal["PENDING_APPROVAL", "APPROVED", "REJECTED", "SUPERSEDED"] = "PENDING_APPROVAL"


class InvestigationAnalysisContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    analysis_run_id: str
    case_id: str
    snapshot_id: str
    status: Literal["COMPLETED", "INSUFFICIENT_EVIDENCE", "BUDGET_EXHAUSTED", "FAILED"]
    summary: str = Field(min_length=1, max_length=4_000)
    evidence: list[EvidenceContract] = Field(default_factory=list, max_length=50)
    hypotheses: list[HypothesisContract] = Field(default_factory=list, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=20)
    required_information: list[str] = Field(default_factory=list, max_length=20)
    termination_reason: str = Field(min_length=1, max_length=512)


class AgentTraceEventContract(ContractModel):
    sequence: int = Field(ge=1)
    event_type: Literal["STARTED", "TOOL_CALL", "TOOL_RESULT", "FINAL", "TERMINATED"]
    iteration: int = Field(ge=0)
    action: str = Field(min_length=1, max_length=128)
    arguments: dict[str, object] = Field(default_factory=dict)
    summary: str = Field(min_length=1, max_length=2_000)
    duration_ms: int | None = Field(default=None, ge=0)
    evidence_ids: list[str] = Field(default_factory=list)


class InvestigationTraceContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    analysis_run_id: str
    events: list[AgentTraceEventContract] = Field(min_length=1, max_length=100)


class InvestigationOutputContract(ContractModel):
    """Atomic application output; analysis and proposal share one run id."""

    analysis: InvestigationAnalysisContract
    proposal: ProposalContract | None = None
    trace: InvestigationTraceContract


class AnalysisRunContract(ContractModel):
    """Durable checkpoint for one automatic or human-requested investigation."""

    analysis_run_id: str
    case_id: str
    snapshot_id: str
    trigger_event_id: str
    idempotency_key: str
    status: Literal[
        "STARTED",
        "COMPLETED",
        "INSUFFICIENT_EVIDENCE",
        "BUDGET_EXHAUSTED",
        "FAILED",
    ]
    started_at: datetime
    completed_at: datetime | None = None
    proposal_id: str | None = None
    trace_event_count: int = Field(default=0, ge=0)
    error_summary: str | None = None

    @model_validator(mode="after")
    def normalize_dates(self) -> "AnalysisRunContract":
        object.__setattr__(self, "started_at", to_utc(self.started_at))
        if self.completed_at is not None:
            object.__setattr__(self, "completed_at", to_utc(self.completed_at))
        return self


class AnalysisStartedEventContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    event_id: str
    event_type: Literal["quality.analysis.started.v1"] = "quality.analysis.started.v1"
    occurred_at: datetime
    analysis_run_id: str
    case_id: str
    snapshot_id: str
    trigger_event_id: str

    @model_validator(mode="after")
    def normalize_occurred_at(self) -> "AnalysisStartedEventContract":
        object.__setattr__(self, "occurred_at", to_utc(self.occurred_at))
        return self


class AnalysisCompletedEventContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    event_id: str
    event_type: Literal["quality.analysis.completed.v1"] = "quality.analysis.completed.v1"
    occurred_at: datetime
    analysis_run_id: str
    case_id: str
    snapshot_id: str
    status: Literal["COMPLETED", "INSUFFICIENT_EVIDENCE", "BUDGET_EXHAUSTED"]
    proposal_id: str | None = None
    trace_event_count: int = Field(ge=0)

    @model_validator(mode="after")
    def normalize_occurred_at(self) -> "AnalysisCompletedEventContract":
        object.__setattr__(self, "occurred_at", to_utc(self.occurred_at))
        return self


class AnalysisFailedEventContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    event_id: str
    event_type: Literal["quality.analysis.failed.v1"] = "quality.analysis.failed.v1"
    occurred_at: datetime
    analysis_run_id: str
    case_id: str
    snapshot_id: str
    error_code: str
    error_summary: str = Field(min_length=1, max_length=512)

    @model_validator(mode="after")
    def normalize_occurred_at(self) -> "AnalysisFailedEventContract":
        object.__setattr__(self, "occurred_at", to_utc(self.occurred_at))
        return self


class InvestigationProposedEventContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    event_id: str
    event_type: Literal["quality.investigation.proposed.v1"] = (
        "quality.investigation.proposed.v1"
    )
    occurred_at: datetime
    proposal: ProposalContract
    analysis_run_id: str
    case_id: str

    @model_validator(mode="after")
    def normalize_occurred_at(self) -> "InvestigationProposedEventContract":
        object.__setattr__(self, "occurred_at", to_utc(self.occurred_at))
        return self
