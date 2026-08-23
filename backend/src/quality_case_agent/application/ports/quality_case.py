"""Ports for Quality Case persistence and event publication."""

from collections.abc import Sequence
from typing import Protocol

from quality_case_agent.domain.quality_case.models import QualityCase, QualityCaseEvent


class QualityCaseStore(Protocol):
    def save_case(self, case: QualityCase) -> None:
        """Persist a case without replacing an immutable snapshot."""

    def record_event(self, event: QualityCaseEvent) -> None:
        """Persist an idempotent case event."""

    def list_cases(self) -> Sequence[QualityCase]:
        """Return cases in deterministic opening-time order."""

    def get_case(self, case_id: str) -> QualityCase | None:
        """Read one case for controlled investigation tools."""
