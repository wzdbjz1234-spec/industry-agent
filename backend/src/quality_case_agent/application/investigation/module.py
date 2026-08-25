"""External Investigation Module interface and request value object."""

from dataclasses import dataclass
from typing import Protocol

from quality_case_agent.contracts.investigation import InvestigationOutputContract


@dataclass(frozen=True, slots=True)
class InvestigationRequest:
    case_id: str
    snapshot_id: str
    analysis_run_id: str | None = None


class InvestigationModule(Protocol):
    def investigate(self, request: InvestigationRequest) -> InvestigationOutputContract:
        """Investigate one immutable Snapshot under policy and budget limits."""
