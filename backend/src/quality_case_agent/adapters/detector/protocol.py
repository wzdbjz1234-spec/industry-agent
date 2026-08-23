"""Detector adapter protocol."""

from collections.abc import Iterator
from typing import Protocol

from quality_case_agent.contracts.inspection import InspectionResultBatchContract


class DetectorAdapter(Protocol):
    def iter_batches(self) -> Iterator[InspectionResultBatchContract]:
        """Yield validated detector batches without exposing model internals."""
