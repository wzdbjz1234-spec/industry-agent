"""Default monitoring policy behind a deliberately small interface."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol

from quality_case_agent.domain.monitoring.drift import (
    cusum_score,
    ewma_zscore,
    kolmogorov_smirnov_distance,
    population_stability_index,
)
from quality_case_agent.domain.monitoring.models import (
    Baseline,
    DriftSignal,
    MonitoringAction,
    MonitoringDecision,
    MonitoringSeverity,
    MonitoringStatus,
    MonitoringWindow,
)


class MonitoringPolicy(Protocol):
    def evaluate(
        self,
        window: MonitoringWindow,
        baseline: Baseline | None,
        *,
        evaluated_at: datetime | None = None,
    ) -> MonitoringDecision:
        """Evaluate one monitoring window without performing I/O."""


class DefaultMonitoringPolicy:
    def __init__(
        self,
        *,
        ewma_threshold: float = 2.0,
        cusum_threshold: float = 2.5,
        psi_threshold: float = 0.2,
        ks_threshold: float = 0.15,
        min_sample_count: int = 5,
        cooldown_minutes: int = 30,
    ) -> None:
        self.ewma_threshold = ewma_threshold
        self.cusum_threshold = cusum_threshold
        self.psi_threshold = psi_threshold
        self.ks_threshold = ks_threshold
        self.min_sample_count = min_sample_count
        self.cooldown_minutes = cooldown_minutes

    def evaluate(
        self,
        window: MonitoringWindow,
        baseline: Baseline | None,
        *,
        evaluated_at: datetime | None = None,
    ) -> MonitoringDecision:
        now = evaluated_at or datetime.now(UTC)
        decision_id = "monitor-" + sha256(
            f"{window.window_start.isoformat()}:{window.dimension_key}:{window.model_version}".encode()
        ).hexdigest()[:20]
        warnings = list(window.warnings)
        if window.total_count < self.min_sample_count:
            warnings.append("INSUFFICIENT_SAMPLE_COUNT")
        if window.late_count > 0:
            warnings.append("LATE_DATA")
        warnings = list(dict.fromkeys(warnings))
        if warnings:
            signal = DriftSignal(
                signal_type="DATA_QUALITY",
                statistic=float(window.late_count or window.total_count),
                threshold=float(self.min_sample_count),
                severity="CRITICAL" if "MIXED_MODEL_VERSIONS" in warnings else "HIGH",
                message="; ".join(warnings),
            )
            return MonitoringDecision(
                decision_id=decision_id,
                evaluated_at=now,
                window=window,
                status="DATA_QUALITY_BLOCK",
                severity=signal.severity,
                action="BLOCK",
                baseline_version=baseline.baseline_version if baseline else None,
                signals=(signal,),
                data_quality_warnings=tuple(warnings),
                cooldown_minutes=self.cooldown_minutes,
            )
        if baseline is None:
            signal = DriftSignal(
                signal_type="DATA_QUALITY",
                statistic=0.0,
                threshold=1.0,
                severity="WARNING",
                message="BASELINE_MISSING",
            )
            return MonitoringDecision(
                decision_id=decision_id,
                evaluated_at=now,
                window=window,
                status="BASELINE_MISSING",
                severity="WARNING",
                action="NONE",
                baseline_version=None,
                signals=(signal,),
                data_quality_warnings=("BASELINE_MISSING",),
                cooldown_minutes=self.cooldown_minutes,
            )

        signals: list[DriftSignal] = []
        score_ewma = ewma_zscore(window.score_mean, baseline.score_mean, baseline.score_std)
        if score_ewma >= self.ewma_threshold:
            signals.append(DriftSignal("EWMA", score_ewma, self.ewma_threshold, "HIGH", "score mean EWMA shift"))
        score_cusum = cusum_score(window.score_mean, baseline.score_mean, baseline.score_std)
        if score_cusum >= self.cusum_threshold:
            signals.append(DriftSignal("CUSUM", score_cusum, self.cusum_threshold, "HIGH", "score mean CUSUM shift"))
        ng_ewma = ewma_zscore(window.ng_rate, baseline.ng_rate_mean, baseline.ng_rate_std)
        if ng_ewma >= self.ewma_threshold:
            signals.append(DriftSignal("EWMA", ng_ewma, self.ewma_threshold, "HIGH", "NG rate EWMA shift"))
        ng_cusum = cusum_score(window.ng_rate, baseline.ng_rate_mean, baseline.ng_rate_std)
        if ng_cusum >= self.cusum_threshold:
            signals.append(DriftSignal("CUSUM", ng_cusum, self.cusum_threshold, "HIGH", "NG rate CUSUM shift"))
        psi = population_stability_index(window.score_histogram, baseline.score_histogram)
        if psi >= self.psi_threshold:
            signals.append(DriftSignal("PSI", psi, self.psi_threshold, "WARNING", "score distribution drift"))
        ks = kolmogorov_smirnov_distance(window.score_histogram, baseline.score_histogram)
        if ks >= self.ks_threshold:
            signals.append(DriftSignal("KS", ks, self.ks_threshold, "WARNING", "score distribution KS drift"))

        process_signals = tuple(signal for signal in signals if signal.signal_type in {"EWMA", "CUSUM"})
        distribution_signals = tuple(signal for signal in signals if signal.signal_type in {"PSI", "KS"})
        if process_signals:
            status: MonitoringStatus = "PROCESS_SHIFT"
            severity: MonitoringSeverity = "HIGH"
            action: MonitoringAction = "OPEN_CASE"
        elif distribution_signals:
            status = "MODEL_DRIFT"
            severity = "WARNING"
            action = "NONE"
        else:
            status = "NORMAL"
            severity = "INFO"
            action = "NONE"
        return MonitoringDecision(
            decision_id=decision_id,
            evaluated_at=now,
            window=window,
            status=status,
            severity=severity,
            action=action,
            baseline_version=baseline.baseline_version,
                signals=tuple(signals),
            data_quality_warnings=(),
            cooldown_minutes=self.cooldown_minutes,
        )
