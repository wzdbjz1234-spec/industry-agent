"""Persistence seam for immutable monitoring baselines."""

from collections.abc import Sequence
from typing import Protocol

from quality_case_agent.domain.monitoring.models import Baseline, DimensionKey


class MonitoringBaselineStore(Protocol):
    def save(self, baseline: Baseline) -> None:
        """Insert or replace a baseline version for one dimension/model shard."""

    def get(self, dimension_key: DimensionKey, model_version: str) -> Baseline | None:
        """Return the latest baseline for a dimension/model shard."""

    def list(self) -> Sequence[Baseline]:
        """Return baselines in deterministic version/key order."""
