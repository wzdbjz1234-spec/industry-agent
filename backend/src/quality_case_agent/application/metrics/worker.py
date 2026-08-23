"""Metrics worker use case."""

from collections.abc import Sequence

from quality_case_agent.application.ports.inspection import InspectionResultStore
from quality_case_agent.application.ports.metrics import QualityMetricsStore
from quality_case_agent.domain.quality_case.metrics import (
    QualityMetricWindow,
    aggregate_quality_metrics,
)


class MetricsWorker:
    """Recompute fixed windows idempotently from persisted inspection facts."""

    def __init__(
        self,
        inspection_store: InspectionResultStore,
        metrics_store: QualityMetricsStore,
    ) -> None:
        self._inspection_store = inspection_store
        self._metrics_store = metrics_store

    def run(self, window_minutes: Sequence[int] = (1, 5)) -> tuple[QualityMetricWindow, ...]:
        results = self._inspection_store.list_results()
        all_windows: list[QualityMetricWindow] = []
        for minutes in window_minutes:
            windows = aggregate_quality_metrics(results, minutes)
            self._metrics_store.upsert_windows(windows)
            all_windows.extend(windows)
        return tuple(all_windows)
