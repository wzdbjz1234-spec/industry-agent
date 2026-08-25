"""Phase 19 baseline, cooldown and persistence integration tests."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from quality_case_agent.adapters.in_memory.monitoring import InMemoryMonitoringBaselineStore
from quality_case_agent.adapters.in_memory.stores import InMemoryInspectionStore
from quality_case_agent.adapters.observability.prometheus import PrometheusMetrics
from quality_case_agent.adapters.postgres.monitoring import SqlAlchemyMonitoringBaselineStore
from quality_case_agent.adapters.postgres.repositories import SqlAlchemyPersistence
from quality_case_agent.application.ingestion.service import InspectionIngestionService
from quality_case_agent.application.monitoring.service import MonitoringService

from simulator.scenarios import ScenarioName, generate_scenario_batches


def _inspection_results():
    store = InMemoryInspectionStore()
    ingestion = InspectionIngestionService(store)
    for batch in generate_scenario_batches(ScenarioName.NORMAL, seed=7):
        ingestion.submit_batch(batch)
    return store, tuple(store.list_results())


def test_monitoring_builds_baseline_and_merges_one_active_case() -> None:
    store, original = _inspection_results()
    baseline_store = InMemoryMonitoringBaselineStore()
    exporter = PrometheusMetrics()
    service = MonitoringService(store, baseline_store, exporter=exporter)
    baselines = service.build_baselines(results=original, baseline_version="normal-v1")
    assert len(baselines) == 1
    assert baseline_store.list()[0].sample_count == len(original)

    shifted = tuple(
        replace(
            result,
            result_id=f"shift-{index}",
            inspected_at=result.inspected_at + timedelta(hours=1),
            is_ng=True,
            anomaly_score=0.90,
        )
        for index, result in enumerate(original[:10])
    )
    first = service.evaluate(results=shifted, evaluated_at=datetime(2026, 8, 25, 10, 0, tzinfo=UTC))
    second = service.evaluate(results=shifted, evaluated_at=datetime(2026, 8, 25, 10, 1, tzinfo=UTC))
    assert first.decisions[0].status == "PROCESS_SHIFT"
    assert first.decisions[0].action == "OPEN_CASE"
    assert second.decisions[0].action == "MERGE_CASE"
    assert b"monitoring_decisions_total" in exporter.render()


def test_late_data_is_blocked_and_missing_baseline_is_explicit() -> None:
    store, original = _inspection_results()
    service = MonitoringService(store, InMemoryMonitoringBaselineStore())
    shifted = tuple(
        replace(result, inspected_at=result.inspected_at - timedelta(hours=1))
        for result in original[:10]
    )
    late = service.evaluate(
        results=shifted,
        watermark=datetime(2026, 8, 25, 10, 0, tzinfo=UTC),
        evaluated_at=datetime(2026, 8, 25, 10, 0, tzinfo=UTC),
    )
    assert late.decisions[0].status == "DATA_QUALITY_BLOCK"
    assert "LATE_DATA" in late.decisions[0].data_quality_warnings

    fresh = service.evaluate(results=original[:10])
    assert fresh.decisions[0].status == "BASELINE_MISSING"


def test_sqlalchemy_baseline_adapter_survives_reopen(tmp_path) -> None:
    _, original = _inspection_results()
    db = SqlAlchemyPersistence(f"sqlite:///{tmp_path / 'monitoring.db'}")
    first_store = SqlAlchemyMonitoringBaselineStore(db)
    service = MonitoringService(InMemoryInspectionStore(), first_store)
    baselines = service.build_baselines(results=original, baseline_version="durable-v1")
    assert len(baselines) == 1

    reopened = SqlAlchemyMonitoringBaselineStore(SqlAlchemyPersistence(f"sqlite:///{tmp_path / 'monitoring.db'}"))
    assert reopened.get(baselines[0].dimension_key, baselines[0].model_version) == baselines[0]
