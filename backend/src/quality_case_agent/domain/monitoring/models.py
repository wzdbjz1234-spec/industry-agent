"""Small, serializable value objects used by the monitoring policy seam."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

DimensionKey = tuple[str, str, str, str]
MonitoringStatus = Literal[
    "NORMAL",
    "PROCESS_SHIFT",
    "MODEL_DRIFT",
    "DATA_QUALITY_BLOCK",
    "BASELINE_MISSING",
]
MonitoringSeverity = Literal["INFO", "WARNING", "HIGH", "CRITICAL"]
MonitoringAction = Literal["NONE", "OPEN_CASE", "MERGE_CASE", "BLOCK"]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class MonitoringWindow:
    window_start: datetime
    window_minutes: int
    factory_id: str
    line_id: str
    station_id: str
    product_id: str
    model_version: str
    total_count: int
    ng_rate: float
    score_mean: float
    score_p95: float
    score_histogram: tuple[float, ...]
    region_shares: tuple[tuple[str, float], ...] = ()
    warnings: tuple[str, ...] = ()
    late_count: int = 0
    watermark: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_start", _utc(self.window_start))
        if self.watermark is not None:
            object.__setattr__(self, "watermark", _utc(self.watermark))
        if self.window_minutes < 1 or self.total_count < 0:
            raise ValueError("window_minutes must be positive and total_count non-negative")
        if any(value < 0 for value in self.score_histogram):
            raise ValueError("score histogram values must be non-negative")

    @property
    def dimension_key(self) -> DimensionKey:
        return self.factory_id, self.line_id, self.station_id, self.product_id

    @property
    def key(self) -> tuple[DimensionKey, str]:
        return self.dimension_key, self.model_version

    @property
    def region_share_map(self) -> dict[str, float]:
        return dict(self.region_shares)

    def as_dict(self) -> dict[str, object]:
        return {
            "window_start": self.window_start.isoformat(),
            "window_minutes": self.window_minutes,
            "factory_id": self.factory_id,
            "line_id": self.line_id,
            "station_id": self.station_id,
            "product_id": self.product_id,
            "model_version": self.model_version,
            "total_count": self.total_count,
            "ng_rate": self.ng_rate,
            "score_mean": self.score_mean,
            "score_p95": self.score_p95,
            "score_histogram": list(self.score_histogram),
            "region_shares": dict(self.region_shares),
            "warnings": list(self.warnings),
            "late_count": self.late_count,
            "watermark": self.watermark.isoformat() if self.watermark else None,
        }


@dataclass(frozen=True, slots=True)
class Baseline:
    baseline_id: str
    baseline_version: str
    created_at: datetime
    dimension_key: DimensionKey
    model_version: str
    sample_count: int
    window_count: int
    ng_rate_mean: float
    ng_rate_std: float
    score_mean: float
    score_std: float
    score_p95: float
    score_histogram: tuple[float, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_at", _utc(self.created_at))
        if self.sample_count < 1 or self.window_count < 1:
            raise ValueError("baseline requires at least one sample and window")

    @property
    def key(self) -> tuple[DimensionKey, str]:
        return self.dimension_key, self.model_version

    def as_dict(self) -> dict[str, object]:
        return {
            "baseline_id": self.baseline_id,
            "baseline_version": self.baseline_version,
            "created_at": self.created_at.isoformat(),
            "dimension_key": list(self.dimension_key),
            "model_version": self.model_version,
            "sample_count": self.sample_count,
            "window_count": self.window_count,
            "ng_rate_mean": self.ng_rate_mean,
            "ng_rate_std": self.ng_rate_std,
            "score_mean": self.score_mean,
            "score_std": self.score_std,
            "score_p95": self.score_p95,
            "score_histogram": list(self.score_histogram),
        }


@dataclass(frozen=True, slots=True)
class DriftSignal:
    signal_type: Literal["EWMA", "CUSUM", "PSI", "KS", "DATA_QUALITY"]
    statistic: float
    threshold: float
    severity: MonitoringSeverity
    message: str

    def as_dict(self) -> dict[str, object]:
        return {
            "signal_type": self.signal_type,
            "statistic": self.statistic,
            "threshold": self.threshold,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class MonitoringDecision:
    decision_id: str
    evaluated_at: datetime
    window: MonitoringWindow
    status: MonitoringStatus
    severity: MonitoringSeverity
    action: MonitoringAction
    baseline_version: str | None
    signals: tuple[DriftSignal, ...]
    data_quality_warnings: tuple[str, ...]
    cooldown_minutes: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "evaluated_at", _utc(self.evaluated_at))

    def as_dict(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "evaluated_at": self.evaluated_at.isoformat(),
            "dimension_key": list(self.window.dimension_key),
            "model_version": self.window.model_version,
            "window_start": self.window.window_start.isoformat(),
            "status": self.status,
            "severity": self.severity,
            "action": self.action,
            "baseline_version": self.baseline_version,
            "signals": [signal.as_dict() for signal in self.signals],
            "data_quality_warnings": list(self.data_quality_warnings),
            "cooldown_minutes": self.cooldown_minutes,
        }
