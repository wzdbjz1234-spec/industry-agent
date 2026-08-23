"""Ports for inspection result persistence."""

from collections.abc import Sequence
from typing import Protocol

from quality_case_agent.domain.inspection.models import InspectionBatch, InspectionResult


class InspectionResultStore(Protocol):
    def insert_batch(self, batch: InspectionBatch) -> tuple[int, int]:
        """Return ``(accepted_count, duplicate_count)``."""

    def list_results(self) -> Sequence[InspectionResult]:
        """Return results in deterministic inspection-time order."""
