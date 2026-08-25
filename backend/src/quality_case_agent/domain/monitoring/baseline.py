"""Deterministic baseline construction for dimension/model shards."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from math import sqrt

from quality_case_agent.domain.monitoring.models import Baseline, MonitoringWindow


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _population_std(values: Sequence[float], mean: float) -> float:
    if len(values) < 2:
        return 0.0
    return sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _normalise(values: Sequence[float]) -> tuple[float, ...]:
    total = sum(values)
    if total <= 0:
        return tuple(1 / len(values) for _ in values) if values else ()
    return tuple(value / total for value in values)


def build_baseline(
    windows: Sequence[MonitoringWindow],
    *,
    baseline_id: str,
    baseline_version: str = "1.0",
    created_at: datetime | None = None,
) -> Baseline:
    """Build one immutable baseline; mixed-model windows are never included."""

    usable = tuple(window for window in windows if "MIXED_MODEL_VERSIONS" not in window.warnings)
    if not usable:
        raise ValueError("at least one non-mixed monitoring window is required")
    keys = {window.key for window in usable}
    if len(keys) != 1:
        raise ValueError("baseline windows must belong to one dimension and model version")
    first = usable[0]
    ng_rates = [window.ng_rate for window in usable]
    score_means = [window.score_mean for window in usable]
    p95_values = [window.score_p95 for window in usable]
    histogram_size = max(len(window.score_histogram) for window in usable)
    histogram = [0.0] * histogram_size
    for window in usable:
        for index, value in enumerate(window.score_histogram):
            histogram[index] += value
    return Baseline(
        baseline_id=baseline_id,
        baseline_version=baseline_version,
        created_at=created_at or datetime.now(UTC),
        dimension_key=first.dimension_key,
        model_version=first.model_version,
        sample_count=sum(window.total_count for window in usable),
        window_count=len(usable),
        ng_rate_mean=_mean(ng_rates),
        ng_rate_std=_population_std(ng_rates, _mean(ng_rates)),
        score_mean=_mean(score_means),
        score_std=_population_std(score_means, _mean(score_means)),
        score_p95=_mean(p95_values),
        score_histogram=_normalise(histogram),
    )
