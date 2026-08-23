"""Replay implementation of the detector adapter boundary."""

from collections.abc import Iterable, Iterator

from quality_case_agent.contracts.inspection import InspectionResultBatchContract


class ReplayDetectorAdapter:
    def __init__(self, batches: Iterable[InspectionResultBatchContract]) -> None:
        self._batches = tuple(batches)

    def iter_batches(self) -> Iterator[InspectionResultBatchContract]:
        yield from self._batches
