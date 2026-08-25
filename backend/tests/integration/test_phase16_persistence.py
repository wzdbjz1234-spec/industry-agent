"""Phase 16 durable adapter contract tests (SQLite exercises PostgreSQL-compatible SQL)."""

from datetime import UTC, datetime

import pytest
from quality_case_agent.adapters.minio.object_store import InMemoryObjectStore
from quality_case_agent.adapters.postgres.repositories import (
    SqlAlchemyAnalysisRunStore,
    SqlAlchemyInspectionStore,
    SqlAlchemyMetricsStore,
    SqlAlchemyPersistence,
    SqlAlchemyQualityCaseStore,
)
from quality_case_agent.application.ingestion.service import InspectionIngestionService
from quality_case_agent.application.metrics.worker import MetricsWorker
from quality_case_agent.bootstrap import build_persistent_resources
from quality_case_agent.config import RuntimeSettings
from quality_case_agent.contracts.investigation import (
    AgentTraceEventContract,
    InvestigationAnalysisContract,
    InvestigationOutputContract,
    InvestigationTraceContract,
)
from quality_case_agent.domain.investigation.models import AnalysisRun

from simulator.scenarios import ScenarioName, generate_scenario_batches


def _stores(tmp_path):
    db = SqlAlchemyPersistence(f"sqlite:///{tmp_path / 'phase16.db'}")
    return (
        SqlAlchemyInspectionStore(db),
        SqlAlchemyMetricsStore(db),
        SqlAlchemyQualityCaseStore(db),
    )


def test_inspection_and_metrics_survive_new_adapter_instance(tmp_path) -> None:
    inspection, metrics, _cases = _stores(tmp_path)
    batch = generate_scenario_batches(ScenarioName.FIXTURE_OFFSET, seed=7)[0]
    receipt = InspectionIngestionService(inspection).submit_batch(batch)
    assert receipt.accepted_count == len(batch.records)
    assert InspectionIngestionService(inspection).submit_batch(batch).accepted_count == 0

    MetricsWorker(inspection, metrics).run(window_minutes=(1, 5))
    assert inspection.count == len(batch.records)
    assert metrics.list_windows()

    inspection2, metrics2, cases2 = _stores(tmp_path)
    assert len(inspection2.list_results()) == len(batch.records)
    assert len(metrics2.list_windows()) == len(metrics.list_windows())
    assert cases2.list_cases() == ()


def test_case_snapshot_is_immutable_and_events_are_idempotent(tmp_path) -> None:
    inspection, metrics, cases = _stores(tmp_path)
    for batch in generate_scenario_batches(ScenarioName.FIXTURE_OFFSET, seed=7):
        InspectionIngestionService(inspection).submit_batch(batch)
    MetricsWorker(inspection, metrics).run(window_minutes=(1, 5))

    from quality_case_agent.application.case_detection.service import QualityCaseDetectionService

    detection = QualityCaseDetectionService(metrics, cases).run()
    assert detection.opened_cases
    case = detection.opened_cases[0]
    cases.save_case(case)
    for event in detection.events:
        cases.record_event(event)
        cases.record_event(event)
    assert len(cases.events) == len({event.event_id for event in detection.events})
    from dataclasses import replace

    changed = replace(case.snapshot, snapshot_id="different")
    case.snapshot = changed
    with pytest.raises(ValueError):
        cases.save_case(case)


def test_analysis_run_and_output_round_trip(tmp_path) -> None:
    db = SqlAlchemyPersistence(f"sqlite:///{tmp_path / 'runs.db'}")
    runs = SqlAlchemyAnalysisRunStore(db)
    run = AnalysisRun(
        analysis_run_id="run-16",
        case_id="case-16",
        snapshot_id="snapshot-16",
        trigger_event_id="event-16",
        idempotency_key="case-16:snapshot-16",
        status="STARTED",
        started_at=datetime.now(UTC),
    )
    runs.save_run(run)
    assert runs.get_by_idempotency_key(run.idempotency_key) is not None
    assert SqlAlchemyAnalysisRunStore(db).get_run("run-16") is not None
    output = InvestigationOutputContract(
        analysis=InvestigationAnalysisContract(
            analysis_run_id="run-16",
            case_id="case-16",
            snapshot_id="snapshot-16",
            status="COMPLETED",
            summary="evidence-backed summary",
            termination_reason="COMPLETED",
        ),
        trace=InvestigationTraceContract(
            analysis_run_id="run-16",
            events=[
                AgentTraceEventContract(
                    sequence=1,
                    event_type="FINAL",
                    iteration=1,
                    action="submit_investigation_analysis",
                    summary="complete",
                )
            ],
        ),
    )
    runs.save_output(output)
    assert SqlAlchemyAnalysisRunStore(db).get_output("run-16") == output
    with pytest.raises(ValueError):
        runs.save_output(output.model_copy(update={"analysis": output.analysis.model_copy(update={"summary": "changed"})}))


def test_bootstrap_builds_a_complete_persistent_resource_bundle(tmp_path) -> None:
    resources = build_persistent_resources(
        RuntimeSettings(mode="test", database_url=f"sqlite:///{tmp_path / 'bootstrap.db'}")
    )
    assert resources.database.engine is not None
    assert resources.inbox.seen("investigation", "missing") is False


def test_inmemory_object_store_round_trip_and_missing_key(tmp_path) -> None:
    store = InMemoryObjectStore()
    uri = store.put("cases/case-16.json", b"{}", content_type="application/json")
    assert uri.startswith("memory://")
    assert store.get("cases/case-16.json") == b"{}"
    assert store.sha256("cases/case-16.json") == "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
    assert store.exists("cases/case-16.json")
    assert not store.exists("missing")
    with pytest.raises(KeyError):
        store.get("missing")
