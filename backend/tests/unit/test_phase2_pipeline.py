"""Phase 2 deterministic ingestion, metrics and Case detection tests."""

from quality_case_agent.adapters.in_memory.stores import (
    InMemoryInspectionStore,
    InMemoryMetricsStore,
    InMemoryQualityCaseStore,
)
from quality_case_agent.application.case_detection.service import QualityCaseDetectionService
from quality_case_agent.application.ingestion.service import InspectionIngestionService
from quality_case_agent.application.metrics.worker import MetricsWorker

from simulator.scenarios import ScenarioName, generate_scenario_batches


def _run_scenario(scenario: ScenarioName):
    inspection_store = InMemoryInspectionStore()
    metrics_store = InMemoryMetricsStore()
    case_store = InMemoryQualityCaseStore()
    ingestion = InspectionIngestionService(inspection_store)
    batches = generate_scenario_batches(scenario, seed=7)
    receipts = [ingestion.submit_batch(batch) for batch in batches]
    MetricsWorker(inspection_store, metrics_store).run(window_minutes=(1, 5))
    detection = QualityCaseDetectionService(metrics_store, case_store).run()
    return inspection_store, metrics_store, case_store, receipts, detection


def test_duplicate_batch_is_idempotent() -> None:
    inspection_store = InMemoryInspectionStore()
    ingestion = InspectionIngestionService(inspection_store)
    batch = generate_scenario_batches(ScenarioName.NORMAL, seed=7)[0]

    first = ingestion.submit_batch(batch)
    second = ingestion.submit_batch(batch)

    assert first.accepted_count == len(batch.records)
    assert second.accepted_count == 0
    assert second.duplicate_count == len(batch.records)
    assert inspection_store.count == len(batch.records)


def test_fixture_offset_metrics_and_case_lifecycle() -> None:
    inspection_store, metrics_store, case_store, receipts, detection = _run_scenario(
        ScenarioName.FIXTURE_OFFSET
    )
    one_minute = [window for window in metrics_store.list_windows() if window.window_minutes == 1]
    abnormal = [window for window in one_minute if window.window_start.minute in {2, 3, 4}]

    assert inspection_store.count == 70
    assert sum(receipt.accepted_count for receipt in receipts) == 70
    assert len(abnormal) == 3
    assert all(window.ng_count == 6 for window in abnormal)
    assert all(window.ng_rate == 0.6 for window in abnormal)
    assert all(window.upper_right_share == 1.0 for window in abnormal)
    assert len(detection.opened_cases) == 1
    assert len(case_store.list_cases()) == 1
    case = case_store.list_cases()[0]
    assert case.case_status == "WAITING_INVESTIGATION"
    assert case.episode_status == "RECOVERED"
    assert {event.event_type for event in case_store.events} == {
        "quality.case.opened.v1",
        "quality.episode.recovered.v1",
    }


def test_non_fixture_scenarios_do_not_open_fixture_offset_cases() -> None:
    for scenario in (
        ScenarioName.NORMAL,
        ScenarioName.ILLUMINATION_DRIFT,
        ScenarioName.INSUFFICIENT_EVIDENCE,
    ):
        _, _, case_store, _, _ = _run_scenario(scenario)
        assert case_store.list_cases() == ()


def test_replay_is_reproducible_for_fixed_seed() -> None:
    first = generate_scenario_batches(ScenarioName.FIXTURE_OFFSET, seed=19)
    second = generate_scenario_batches(ScenarioName.FIXTURE_OFFSET, seed=19)
    assert [batch.model_dump(mode="json") for batch in first] == [
        batch.model_dump(mode="json") for batch in second
    ]
