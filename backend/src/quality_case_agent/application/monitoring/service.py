"""Monitoring orchestration: build windows, persist baselines, evaluate policy."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from math import floor

from quality_case_agent.application.ports.inspection import InspectionResultStore
from quality_case_agent.application.ports.monitoring import MonitoringBaselineStore
from quality_case_agent.domain.inspection.models import InspectionResult
from quality_case_agent.domain.monitoring.baseline import build_baseline
from quality_case_agent.domain.monitoring.models import (
    Baseline,
    MonitoringDecision,
    MonitoringWindow,
)
from quality_case_agent.domain.monitoring.policies import DefaultMonitoringPolicy, MonitoringPolicy


@dataclass(frozen=True, slots=True)
class MonitoringReport:
    evaluated_at: datetime
    windows: tuple[MonitoringWindow, ...]
    decisions: tuple[MonitoringDecision, ...]
    baselines: tuple[Baseline, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "evaluated_at": self.evaluated_at.isoformat(),
            "window_count": len(self.windows),
            "baseline_count": len(self.baselines),
            "windows": [window.as_dict() for window in self.windows],
            "decisions": [decision.as_dict() for decision in self.decisions],
            "baselines": [baseline.as_dict() for baseline in self.baselines],
        }


class MonitoringService:
    """Deep monitoring module with a small interface and deterministic outcomes."""

    def __init__(
        self,
        inspection_store: InspectionResultStore,
        baseline_store: MonitoringBaselineStore,
        *,
        policy: MonitoringPolicy | None = None,
        allowed_lateness: timedelta = timedelta(minutes=2),
        exporter: object | None = None,
    ) -> None:
        self._inspection_store = inspection_store
        self._baseline_store = baseline_store
        self._policy = policy or DefaultMonitoringPolicy()
        self._allowed_lateness = allowed_lateness
        self._exporter = exporter
        self._active_case_until: dict[tuple[tuple[str, str, str, str], str], datetime] = {}

    def build_baselines(
        self,
        *,
        window_minutes: int = 1,
        baseline_version: str = "1.0",
        results: Sequence[InspectionResult] | None = None,
    ) -> tuple[Baseline, ...]:
        windows = self.build_windows(
            results if results is not None else self._inspection_store.list_results(),
            window_minutes=window_minutes,
        )
        grouped: dict[tuple[tuple[str, str, str, str], str], list[MonitoringWindow]] = defaultdict(list)
        for window in windows:
            grouped[window.key].append(window)
        baselines: list[Baseline] = []
        for key, shard_windows in sorted(grouped.items(), key=lambda item: item[0]):
            if any("MIXED_MODEL_VERSIONS" in window.warnings for window in shard_windows):
                continue
            dimension_key, model_version = key
            fingerprint = sha256(f"{dimension_key}:{model_version}:{baseline_version}".encode()).hexdigest()[:16]
            baseline = build_baseline(
                tuple(shard_windows),
                baseline_id=f"baseline-{fingerprint}",
                baseline_version=baseline_version,
            )
            self._baseline_store.save(baseline)
            baselines.append(baseline)
        return tuple(baselines)

    def evaluate(
        self,
        *,
        window_minutes: int = 1,
        watermark: datetime | None = None,
        results: Sequence[InspectionResult] | None = None,
        evaluated_at: datetime | None = None,
    ) -> MonitoringReport:
        now = _utc(evaluated_at or datetime.now(UTC))
        windows = self.build_windows(
            results if results is not None else self._inspection_store.list_results(),
            window_minutes=window_minutes,
            watermark=watermark,
        )
        decisions: list[MonitoringDecision] = []
        for window in windows:
            baseline = self._baseline_store.get(window.dimension_key, window.model_version)
            decision = self._policy.evaluate(window, baseline, evaluated_at=now)
            decision = self._apply_cooldown(decision, now)
            decisions.append(decision)
            record_monitoring = getattr(self._exporter, "record_monitoring", None)
            if callable(record_monitoring):
                record_monitoring(decision)
        return MonitoringReport(
            evaluated_at=now,
            windows=windows,
            decisions=tuple(decisions),
            baselines=tuple(self._baseline_store.list()),
        )

    def build_windows(
        self,
        results: Sequence[InspectionResult],
        *,
        window_minutes: int = 1,
        watermark: datetime | None = None,
    ) -> tuple[MonitoringWindow, ...]:
        if window_minutes < 1:
            raise ValueError("window_minutes must be positive")
        normalized_watermark = _utc(watermark) if watermark else None
        grouped: dict[tuple[datetime, tuple[str, str, str, str]], list[InspectionResult]] = defaultdict(list)
        for result in results:
            start = result.inspected_at.astimezone(UTC).replace(
                minute=(result.inspected_at.minute // window_minutes) * window_minutes,
                second=0,
                microsecond=0,
            )
            grouped[(start, result.dimension_key)].append(result)
        windows: list[MonitoringWindow] = []
        for (window_start, dimension_key), group in sorted(grouped.items(), key=lambda item: item[0]):
            model_versions = {result.detector.model_version for result in group}
            model_version = next(iter(model_versions)) if len(model_versions) == 1 else "MIXED"
            warnings: list[str] = []
            if len(model_versions) > 1:
                warnings.append("MIXED_MODEL_VERSIONS")
            if len(group) < 5:
                warnings.append("INSUFFICIENT_SAMPLE_COUNT")
            late_count = 0
            if normalized_watermark is not None:
                late_count = sum(
                    result.inspected_at < normalized_watermark - self._allowed_lateness
                    for result in group
                )
                if late_count:
                    warnings.append("LATE_DATA")
            scores = [result.anomaly_score for result in group]
            histogram = [0.0] * 10
            for score in scores:
                histogram[min(9, max(0, floor(score * 10)))] += 1
            ng_count = sum(result.is_ng for result in group)
            region_counts: dict[str, int] = defaultdict(int)
            for result in group:
                if result.is_ng and result.defect_region is not None:
                    region_counts[result.defect_region.region_label] += 1
            region_shares = tuple(
                sorted((label, count / ng_count) for label, count in region_counts.items())
            ) if ng_count else ()
            dimensions = dimension_key
            windows.append(
                MonitoringWindow(
                    window_start=window_start,
                    window_minutes=window_minutes,
                    factory_id=dimensions[0],
                    line_id=dimensions[1],
                    station_id=dimensions[2],
                    product_id=dimensions[3],
                    model_version=model_version,
                    total_count=len(group),
                    ng_rate=ng_count / len(group),
                    score_mean=sum(scores) / len(scores),
                    score_p95=sorted(scores)[max(0, floor(len(scores) * 0.95) - 1)],
                    score_histogram=tuple(histogram),
                    region_shares=region_shares,
                    warnings=tuple(dict.fromkeys(warnings)),
                    late_count=late_count,
                    watermark=normalized_watermark,
                )
            )
        return tuple(windows)

    def _apply_cooldown(self, decision: MonitoringDecision, now: datetime) -> MonitoringDecision:
        key = decision.window.key
        if decision.action == "OPEN_CASE":
            active_until = self._active_case_until.get(key)
            if active_until is not None and active_until > now:
                from dataclasses import replace

                return replace(decision, action="MERGE_CASE")
            self._active_case_until[key] = now + timedelta(minutes=decision.cooldown_minutes)
        elif decision.status == "NORMAL":
            self._active_case_until.pop(key, None)
        return decision


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
