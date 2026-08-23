"""Run the offline Phase 2 replay and print a JSON summary."""

from __future__ import annotations

import json

from quality_case_agent.adapters.in_memory.stores import (
    InMemoryInspectionStore,
    InMemoryMetricsStore,
    InMemoryQualityCaseStore,
)
from quality_case_agent.application.case_detection.service import QualityCaseDetectionService
from quality_case_agent.application.ingestion.service import InspectionIngestionService
from quality_case_agent.application.metrics.worker import MetricsWorker

from simulator.replay import scenario_replay
from simulator.scenarios import ScenarioName


def main() -> int:
    inspection_store = InMemoryInspectionStore()
    metrics_store = InMemoryMetricsStore()
    case_store = InMemoryQualityCaseStore()
    ingestion = InspectionIngestionService(inspection_store)

    batches = tuple(scenario_replay(ScenarioName.FIXTURE_OFFSET, seed=7, batch_size=10))
    receipts = [ingestion.submit_batch(batch) for batch in batches]
    duplicate_receipt = ingestion.submit_batch(batches[0])

    MetricsWorker(inspection_store, metrics_store).run(window_minutes=(1, 5))
    detection = QualityCaseDetectionService(metrics_store, case_store).run(window_minutes=1)

    summary = {
        "scenario": ScenarioName.FIXTURE_OFFSET.value,
        "batch_count": len(batches),
        "result_count": inspection_store.count,
        "duplicate_first_batch": {
            "accepted_count": duplicate_receipt.accepted_count,
            "duplicate_count": duplicate_receipt.duplicate_count,
        },
        "metric_window_count": len(metrics_store.list_windows()),
        "opened_case_count": len(detection.opened_cases),
        "case_count": len(case_store.list_cases()),
        "events": [event.event_type for event in case_store.events],
        "cases": [
            {
                "case_id": case.case_id,
                "trigger_family": case.trigger_family,
                "case_status": case.case_status,
                "episode_status": case.episode_status,
                "snapshot_hash": case.snapshot.snapshot_hash,
            }
            for case in case_store.list_cases()
        ],
        "accepted_counts": [receipt.accepted_count for receipt in receipts],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
