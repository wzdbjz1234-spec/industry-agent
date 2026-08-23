"""Deterministic event detectors for quality-case trigger families."""

from dataclasses import dataclass, field
from typing import Protocol

from .metrics import QualityMetricWindow
from .models import QualityCase, QualityCaseEvent, QualityCaseSnapshot


@dataclass(frozen=True, slots=True)
class FixtureOffsetRules:
    ng_rate_threshold: float = 0.35
    upper_right_share_threshold: float = 0.60
    open_after_windows: int = 3
    recover_after_windows: int = 2


@dataclass(slots=True)
class _EpisodeState:
    violation_windows: list[QualityMetricWindow] = field(default_factory=list)
    recovery_count: int = 0
    active_case: QualityCase | None = None


@dataclass(frozen=True, slots=True)
class CaseDetectionResult:
    opened_cases: tuple[QualityCase, ...]
    updated_cases: tuple[QualityCase, ...]
    events: tuple[QualityCaseEvent, ...]


class CaseDetector(Protocol):
    def detect(self, windows: tuple[QualityMetricWindow, ...]) -> CaseDetectionResult:
        """Detect immutable Case snapshots from metric windows."""


class FixtureOffsetCaseDetector:
    """Detect one Case per continuous Fixture Offset episode."""

    def __init__(self, rules: FixtureOffsetRules | None = None) -> None:
        self.rules = rules or FixtureOffsetRules()

    def detect(self, windows: tuple[QualityMetricWindow, ...]) -> CaseDetectionResult:
        states: dict[tuple[str, str, str, str], _EpisodeState] = {}
        opened: list[QualityCase] = []
        updated: list[QualityCase] = []
        events: list[QualityCaseEvent] = []

        for window in sorted(windows, key=lambda item: (item.dimension_key, item.window_start)):
            state = states.setdefault(window.dimension_key, _EpisodeState())
            violates = (
                window.ng_rate >= self.rules.ng_rate_threshold
                and window.upper_right_share >= self.rules.upper_right_share_threshold
            )
            if violates:
                state.recovery_count = 0
                if state.active_case is not None and state.active_case.episode_status == "ACTIVE":
                    state.violation_windows.clear()
                state.violation_windows.append(window)
                if (
                    state.active_case is None or state.active_case.episode_status == "RECOVERED"
                ) and len(state.violation_windows) >= self.rules.open_after_windows:
                    evidence = tuple(state.violation_windows[-self.rules.open_after_windows :])
                    case = self._open_case(evidence)
                    state.active_case = case
                    state.violation_windows.clear()
                    opened.append(case)
                    events.append(
                        QualityCaseEvent(
                            event_type="quality.case.opened.v1",
                            case_id=case.case_id,
                            occurred_at=case.opened_at,
                            snapshot_id=case.snapshot.snapshot_id,
                        )
                    )
            elif state.active_case is not None and state.active_case.episode_status == "ACTIVE":
                state.recovery_count += 1
                if state.recovery_count >= self.rules.recover_after_windows:
                    state.violation_windows.clear()
                    state.active_case.mark_recovered(window.window_end)
                    updated.append(state.active_case)
                    events.append(
                        QualityCaseEvent(
                            event_type="quality.episode.recovered.v1",
                            case_id=state.active_case.case_id,
                            occurred_at=window.window_end,
                        )
                    )
            else:
                state.violation_windows.clear()

        return CaseDetectionResult(tuple(opened), tuple(updated), tuple(events))

    @staticmethod
    def _open_case(evidence: tuple[QualityMetricWindow, ...]) -> QualityCase:
        first = evidence[0]
        fingerprint = ":".join(first.dimension_key + ("FIXTURE_OFFSET",))
        opened_at = evidence[-1].window_end
        case_id = (
            f"qc-{first.factory_id}-{first.station_id}-{first.product_id}-"
            f"{first.window_start:%Y%m%dT%H%MZ}"
        )
        baseline = evidence[0]
        snapshot = QualityCaseSnapshot(
            snapshot_id=f"{case_id}-snapshot-01",
            case_id=case_id,
            created_at=opened_at,
            trigger_family="FIXTURE_OFFSET",
            observations=evidence,
            lookback_window_minutes=sum(window.window_minutes for window in evidence),
            baseline_ng_rate=baseline.ng_rate,
            baseline_score_mean=baseline.score_mean,
            data_quality_warnings=tuple(
                sorted({warning for window in evidence for warning in window.warnings})
            ),
        )
        return QualityCase(
            case_id=case_id,
            fingerprint=fingerprint,
            trigger_family="FIXTURE_OFFSET",
            opened_at=opened_at,
            snapshot=snapshot,
        )


@dataclass(frozen=True, slots=True)
class IlluminationDriftRules:
    score_mean_threshold: float = 0.50
    ng_rate_threshold: float = 0.40
    min_region_count: int = 4
    open_after_windows: int = 3


class IlluminationDriftCaseDetector:
    """Open one Case when score/NG rates rise without a single defect cluster."""

    def __init__(self, rules: IlluminationDriftRules | None = None) -> None:
        self.rules = rules or IlluminationDriftRules()

    def detect(self, windows: tuple[QualityMetricWindow, ...]) -> CaseDetectionResult:
        grouped: dict[tuple[str, str, str, str], list[QualityMetricWindow]] = {}
        for window in sorted(windows, key=lambda item: (item.dimension_key, item.window_start)):
            grouped.setdefault(window.dimension_key, []).append(window)
        opened: list[QualityCase] = []
        events: list[QualityCaseEvent] = []
        for dimension_windows in grouped.values():
            violating = [
                window
                for window in dimension_windows
                if (
                    window.score_mean >= self.rules.score_mean_threshold
                    and window.ng_rate >= self.rules.ng_rate_threshold
                    and len(window.region_counts) >= self.rules.min_region_count
                )
            ]
            if len(violating) < self.rules.open_after_windows:
                continue
            evidence = tuple(violating[-self.rules.open_after_windows :])
            case = self._open_case(evidence)
            opened.append(case)
            events.append(
                QualityCaseEvent(
                    event_type="quality.case.opened.v1",
                    case_id=case.case_id,
                    occurred_at=case.opened_at,
                    snapshot_id=case.snapshot.snapshot_id,
                )
            )
        return CaseDetectionResult(tuple(opened), (), tuple(events))

    @staticmethod
    def _open_case(evidence: tuple[QualityMetricWindow, ...]) -> QualityCase:
        first = evidence[0]
        fingerprint = ":".join(first.dimension_key + ("ILLUMINATION_DRIFT",))
        case_id = (
            f"qc-{first.factory_id}-{first.station_id}-{first.product_id}-"
            f"{first.window_start:%Y%m%dT%H%MZ}-illumination"
        )
        opened_at = evidence[-1].window_end
        snapshot = QualityCaseSnapshot(
            snapshot_id=f"{case_id}-snapshot-01",
            case_id=case_id,
            created_at=opened_at,
            trigger_family="ILLUMINATION_DRIFT",
            observations=evidence,
            lookback_window_minutes=sum(window.window_minutes for window in evidence),
            baseline_ng_rate=first.ng_rate,
            baseline_score_mean=first.score_mean,
            data_quality_warnings=tuple(
                sorted({warning for window in evidence for warning in window.warnings})
            ),
        )
        return QualityCase(
            case_id=case_id,
            fingerprint=fingerprint,
            trigger_family="ILLUMINATION_DRIFT",
            opened_at=opened_at,
            snapshot=snapshot,
        )


@dataclass(frozen=True, slots=True)
class InsufficientEvidenceRules:
    warning_codes: frozenset[str] = frozenset(
        {"INSUFFICIENT_SAMPLE_COUNT", "MIXED_MODEL_VERSIONS", "DATA_MISSING"}
    )


class InsufficientEvidenceCaseDetector:
    """Open a data-quality Case as soon as a window cannot support RCA."""

    def __init__(self, rules: InsufficientEvidenceRules | None = None) -> None:
        self.rules = rules or InsufficientEvidenceRules()

    def detect(self, windows: tuple[QualityMetricWindow, ...]) -> CaseDetectionResult:
        candidates = [
            window
            for window in sorted(windows, key=lambda item: (item.dimension_key, item.window_start))
            if self.rules.warning_codes.intersection(window.warnings)
        ]
        if not candidates:
            return CaseDetectionResult((), (), ())
        first = candidates[0]
        case_id = (
            f"qc-{first.factory_id}-{first.station_id}-{first.product_id}-"
            f"{first.window_start:%Y%m%dT%H%MZ}-data-quality"
        )
        snapshot = QualityCaseSnapshot(
            snapshot_id=f"{case_id}-snapshot-01",
            case_id=case_id,
            created_at=first.window_end,
            trigger_family="DATA_QUALITY_BLOCKED",
            observations=(first,),
            lookback_window_minutes=first.window_minutes,
            baseline_ng_rate=first.ng_rate,
            baseline_score_mean=first.score_mean,
            data_quality_warnings=tuple(sorted(self.rules.warning_codes.intersection(first.warnings))),
        )
        case = QualityCase(
            case_id=case_id,
            fingerprint=":".join(first.dimension_key + ("DATA_QUALITY_BLOCKED",)),
            trigger_family="DATA_QUALITY_BLOCKED",
            opened_at=first.window_end,
            snapshot=snapshot,
        )
        event = QualityCaseEvent(
            event_type="quality.case.opened.v1",
            case_id=case_id,
            occurred_at=first.window_end,
            snapshot_id=snapshot.snapshot_id,
        )
        return CaseDetectionResult((case,), (), (event,))
