"""Phase 19 policy tests through the monitoring module interface."""

from datetime import UTC, datetime, timedelta

from quality_case_agent.domain.monitoring.baseline import build_baseline
from quality_case_agent.domain.monitoring.models import MonitoringWindow
from quality_case_agent.domain.monitoring.policies import DefaultMonitoringPolicy

START = datetime(2026, 8, 25, 8, 0, tzinfo=UTC)


def _window(
    minute: int,
    *,
    score_mean: float = 0.20,
    histogram: tuple[float, ...] = (0, 0, 10, 0, 0, 0, 0, 0, 0, 0),
    warnings: tuple[str, ...] = (),
    total_count: int = 10,
    late_count: int = 0,
) -> MonitoringWindow:
    return MonitoringWindow(
        window_start=START + timedelta(minutes=minute),
        window_minutes=1,
        factory_id="factory-01",
        line_id="line-01",
        station_id="camera-01",
        product_id="part-A",
        model_version="model-1",
        total_count=total_count,
        ng_rate=0.05,
        score_mean=score_mean,
        score_p95=score_mean + 0.05,
        score_histogram=histogram,
        warnings=warnings,
        late_count=late_count,
    )


def _baseline() -> object:
    return build_baseline(
        tuple(_window(index, score_mean=0.18 + index * 0.01) for index in range(5)),
        baseline_id="baseline-test",
        baseline_version="2026-08-25",
        created_at=START,
    )


def test_normal_window_has_no_case_action() -> None:
    decision = DefaultMonitoringPolicy().evaluate(_window(10, score_mean=0.20), _baseline(), evaluated_at=START)
    assert decision.status == "NORMAL"
    assert decision.action == "NONE"
    assert decision.signals == ()


def test_ewma_and_cusum_identify_process_shift() -> None:
    decision = DefaultMonitoringPolicy().evaluate(_window(10, score_mean=0.85), _baseline(), evaluated_at=START)
    assert decision.status == "PROCESS_SHIFT"
    assert decision.action == "OPEN_CASE"
    assert {signal.signal_type for signal in decision.signals} >= {"EWMA", "CUSUM"}


def test_psi_and_ks_identify_model_or_input_drift_without_case() -> None:
    decision = DefaultMonitoringPolicy().evaluate(
        _window(10, score_mean=0.22, histogram=(0, 0, 0, 0, 0, 0, 0, 10, 0, 0)),
        _baseline(),
        evaluated_at=START,
    )
    assert decision.status == "MODEL_DRIFT"
    assert decision.action == "NONE"
    assert {signal.signal_type for signal in decision.signals} >= {"PSI", "KS"}


def test_data_quality_blocks_case_opening() -> None:
    decision = DefaultMonitoringPolicy().evaluate(
        _window(10, warnings=("MIXED_MODEL_VERSIONS",), late_count=2),
        _baseline(),
        evaluated_at=START,
    )
    assert decision.status == "DATA_QUALITY_BLOCK"
    assert decision.action == "BLOCK"
    assert "MIXED_MODEL_VERSIONS" in decision.data_quality_warnings
    assert decision.severity == "CRITICAL"
