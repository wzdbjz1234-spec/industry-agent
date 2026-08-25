"""In-memory baseline adapter used by tests and the offline demo."""

from collections.abc import Sequence

from quality_case_agent.domain.monitoring.models import Baseline, DimensionKey


class InMemoryMonitoringBaselineStore:
    def __init__(self) -> None:
        self._baselines: dict[tuple[DimensionKey, str], Baseline] = {}

    def save(self, baseline: Baseline) -> None:
        self._baselines[baseline.key] = baseline

    def get(self, dimension_key: DimensionKey, model_version: str) -> Baseline | None:
        return self._baselines.get((dimension_key, model_version))

    def list(self) -> Sequence[Baseline]:
        return tuple(
            self._baselines[key]
            for key in sorted(self._baselines, key=lambda item: (item[0], item[1]))
        )
