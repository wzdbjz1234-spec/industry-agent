"""Quality Case detection use case."""

from quality_case_agent.application.ports.metrics import QualityMetricsStore
from quality_case_agent.application.ports.quality_case import QualityCaseStore
from quality_case_agent.domain.quality_case.detector import (
    CaseDetectionResult,
    CaseDetector,
    FixtureOffsetCaseDetector,
)


class QualityCaseDetectionService:
    """Run event detection against stored metric windows."""

    def __init__(
        self,
        metrics_store: QualityMetricsStore,
        case_store: QualityCaseStore,
        detector: CaseDetector | None = None,
    ) -> None:
        self._metrics_store = metrics_store
        self._case_store = case_store
        self._detector = detector or FixtureOffsetCaseDetector()

    def run(self, window_minutes: int = 1) -> CaseDetectionResult:
        windows = tuple(
            window
            for window in self._metrics_store.list_windows()
            if window.window_minutes == window_minutes
        )
        result = self._detector.detect(windows)
        for case in result.opened_cases:
            self._case_store.save_case(case)
        for case in result.updated_cases:
            self._case_store.save_case(case)
        for event in result.events:
            self._case_store.record_event(event)
        return result
