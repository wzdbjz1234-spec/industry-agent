"""Ports for metric-window persistence."""

from collections.abc import Sequence
from typing import Protocol

from quality_case_agent.domain.quality_case.metrics import QualityMetricWindow


class QualityMetricsStore(Protocol):
    def upsert_windows(self, windows: Sequence[QualityMetricWindow]) -> int:
        """Insert or replace windows and return the number processed."""

    def list_windows(self) -> Sequence[QualityMetricWindow]:
        """Return stored windows in deterministic order."""
