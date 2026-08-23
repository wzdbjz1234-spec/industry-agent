"""Deterministic fixed-window quality metric aggregation."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from math import ceil

from quality_case_agent.domain.inspection.models import InspectionResult


@dataclass(frozen=True, slots=True)
class QualityMetricWindow:
    window_start: datetime
    window_minutes: int
    factory_id: str
    line_id: str
    station_id: str
    product_id: str
    total_count: int
    ng_count: int
    ng_rate: float
    score_mean: float
    score_p95: float
    region_counts: tuple[tuple[str, int], ...]
    model_versions: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def window_end(self) -> datetime:
        from datetime import timedelta

        return self.window_start + timedelta(minutes=self.window_minutes)

    @property
    def region_shares(self) -> dict[str, float]:
        if self.ng_count == 0:
            return {}
        return {label: count / self.ng_count for label, count in self.region_counts}

    @property
    def upper_right_share(self) -> float:
        return self.region_shares.get("upper_right", 0.0)

    @property
    def dimension_key(self) -> tuple[str, str, str, str]:
        return self.factory_id, self.line_id, self.station_id, self.product_id

    def as_dict(self) -> dict[str, object]:
        return {
            "window_start": self.window_start.isoformat(),
            "window_minutes": self.window_minutes,
            "factory_id": self.factory_id,
            "line_id": self.line_id,
            "station_id": self.station_id,
            "product_id": self.product_id,
            "total_count": self.total_count,
            "ng_count": self.ng_count,
            "ng_rate": self.ng_rate,
            "score_mean": self.score_mean,
            "score_p95": self.score_p95,
            "region_counts": dict(self.region_counts),
            "model_versions": list(self.model_versions),
            "warnings": list(self.warnings),
        }


def _window_start(value: datetime, window_minutes: int) -> datetime:
    if window_minutes not in {1, 5}:
        raise ValueError("only 1-minute and 5-minute windows are supported")
    return value.replace(
        minute=(value.minute // window_minutes) * window_minutes,
        second=0,
        microsecond=0,
    )


def _nearest_rank_p95(scores: list[float]) -> float:
    ordered = sorted(scores)
    rank = max(1, ceil(len(ordered) * 0.95))
    return ordered[rank - 1]


def aggregate_quality_metrics(
    results: Iterable[InspectionResult], window_minutes: int
) -> tuple[QualityMetricWindow, ...]:
    """Aggregate inspection results into deterministic fixed windows."""

    grouped: dict[tuple[datetime, tuple[str, str, str, str]], list[InspectionResult]] = {}
    for result in results:
        key = (_window_start(result.inspected_at, window_minutes), result.dimension_key)
        grouped.setdefault(key, []).append(result)

    windows: list[QualityMetricWindow] = []
    for (window_start, dimensions), group in sorted(grouped.items(), key=lambda item: item[0]):
        factory_id, line_id, station_id, product_id = dimensions
        scores = [result.anomaly_score for result in group]
        ng_results = [result for result in group if result.is_ng]
        region_counts: dict[str, int] = {}
        for result in ng_results:
            if result.defect_region is not None:
                label = result.defect_region.region_label
                region_counts[label] = region_counts.get(label, 0) + 1
        model_versions = tuple(sorted({result.detector.model_version for result in group}))
        warning_values: list[str] = []
        if len(model_versions) > 1:
            warning_values.append("MIXED_MODEL_VERSIONS")
        if len(group) < 5:
            warning_values.append("INSUFFICIENT_SAMPLE_COUNT")
        warnings = tuple(warning_values)
        windows.append(
            QualityMetricWindow(
                window_start=window_start,
                window_minutes=window_minutes,
                factory_id=factory_id,
                line_id=line_id,
                station_id=station_id,
                product_id=product_id,
                total_count=len(group),
                ng_count=len(ng_results),
                ng_rate=len(ng_results) / len(group),
                score_mean=sum(scores) / len(scores),
                score_p95=_nearest_rank_p95(scores),
                region_counts=tuple(sorted(region_counts.items())),
                model_versions=model_versions,
                warnings=warnings,
            )
        )
    return tuple(windows)
