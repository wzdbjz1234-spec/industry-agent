"""Validated, data-only investigation Runbook contracts."""

from typing import Literal

from pydantic import Field

from .common import ContractModel
from .investigation import ProposalStepContract


class RunbookHypothesisContract(ContractModel):
    hypothesis_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=2_000)
    default_confidence: float = Field(ge=0.0, le=1.0)
    missing_evidence: list[str] = Field(default_factory=list, max_length=20)


class RunbookProposalContract(ContractModel):
    title: str = Field(min_length=1, max_length=256)
    reason: str = Field(min_length=1, max_length=2_000)
    steps: list[ProposalStepContract] = Field(min_length=1, max_length=20)
    requested_role: str = Field(min_length=1, max_length=128)
    priority: Literal["LOW", "MEDIUM", "HIGH"]
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]


class RunbookContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    runbook_id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    trigger_family: str = Field(min_length=1, max_length=128)
    required_tools: list[str] = Field(min_length=1, max_length=20)
    knowledge_query: str = Field(min_length=1, max_length=512)
    candidate_hypotheses: list[RunbookHypothesisContract] = Field(min_length=1, max_length=20)
    proposal: RunbookProposalContract | None = None


class HypothesisDraftContract(ContractModel):
    """Structured, non-authoritative hypothesis draft returned by an LLM."""

    hypothesis_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=2_000)
    confidence: float = Field(ge=0.0, le=1.0)
    missing_evidence: list[str] = Field(default_factory=list, max_length=20)


class InvestigationDraftContract(ContractModel):
    """Draft data is validated before it can influence the grounded output."""

    hypothesis: HypothesisDraftContract | None = None
    proposal: RunbookProposalContract | None = None
