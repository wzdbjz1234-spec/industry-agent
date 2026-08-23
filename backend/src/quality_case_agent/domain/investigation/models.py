"""Pure investigation value objects shared by application ports and adapters."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True, slots=True)
class ToolObservation:
    """Safe, summarized tool output recorded in an Agent Trace."""

    tool_name: str
    success: bool
    summary: str
    payload: Mapping[str, object]
    evidence_ids: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "summary": self.summary,
            "payload": dict(self.payload),
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(slots=True)
class AnalysisRun:
    """Mutable checkpoint state; the analysis output itself remains immutable by run ID."""

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
    trace_event_count: int = 0
    error_summary: str | None = None
