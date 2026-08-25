"""Runbook value objects with no executable code or provider dependencies."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RunbookHypothesis:
    hypothesis_id: str
    title: str
    description: str
    default_confidence: float
    missing_evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RunbookStep:
    order: int
    instruction: str
    expected_evidence: str


@dataclass(frozen=True, slots=True)
class RunbookProposal:
    title: str
    reason: str
    steps: tuple[RunbookStep, ...]
    requested_role: str
    priority: str
    risk_level: str


@dataclass(frozen=True, slots=True)
class Runbook:
    runbook_id: str
    version: str
    trigger_family: str
    required_tools: tuple[str, ...]
    knowledge_query: str
    candidate_hypotheses: tuple[RunbookHypothesis, ...]
    proposal: RunbookProposal | None
