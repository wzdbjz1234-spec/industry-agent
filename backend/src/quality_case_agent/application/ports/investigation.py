"""Ports for safe investigation tools."""

from collections.abc import Sequence
from typing import Protocol

from quality_case_agent.contracts.investigation import InvestigationOutputContract
from quality_case_agent.domain.investigation.models import AnalysisRun, ToolObservation


class InvestigationTool(Protocol):
    @property
    def name(self) -> str: ...

    def invoke(self, arguments: dict[str, object]) -> ToolObservation:
        """Execute a validated, read-only tool call."""


class AnalysisRunStore(Protocol):
    def get_by_idempotency_key(self, key: str) -> AnalysisRun | None:
        """Find an existing automatic run before executing the Agent."""

    def get_run(self, analysis_run_id: str) -> AnalysisRun | None:
        """Load a checkpoint by run ID."""

    def save_run(self, run: AnalysisRun) -> None:
        """Persist a checkpoint transition."""

    def save_output(self, output: InvestigationOutputContract) -> None:
        """Persist the structured output and trace by run ID."""

    def get_output(self, analysis_run_id: str) -> InvestigationOutputContract | None:
        """Return a previously completed output for idempotent replay."""

    def list_runs(self) -> Sequence[AnalysisRun]:
        """Return runs in deterministic start order."""


class InvestigationEventPublisher(Protocol):
    def publish(self, event: object) -> None:
        """Publish a validated analysis lifecycle event idempotently."""


class ReanalysisRequester(Protocol):
    def reanalyze(self, case_id: str, snapshot_id: str, request_id: str) -> str:
        """Start a fresh run against the same immutable snapshot."""
