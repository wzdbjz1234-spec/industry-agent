"""Run the 60-second offline demo path without Docker, GPU or external APIs."""

from __future__ import annotations

import json

from quality_case_agent.application.case_detection.service import QualityCaseDetectionService
from quality_case_agent.application.ingestion.service import InspectionIngestionService
from quality_case_agent.application.metrics.worker import MetricsWorker
from quality_case_agent.entrypoints.api.app import build_demo_container

from simulator.replay import scenario_replay
from simulator.scenarios import ScenarioName


def main() -> int:
    container = build_demo_container()
    for batch in scenario_replay(ScenarioName.FIXTURE_OFFSET, seed=7, batch_size=10):
        InspectionIngestionService(container.inspection).submit_batch(batch)
    MetricsWorker(container.inspection, container.metrics).run(window_minutes=(1, 5))
    detection = QualityCaseDetectionService(container.metrics, container.cases).run()
    for event in detection.events:
        if event.event_type == "quality.case.opened.v1":
            container.investigations.handle_case_opened(event)
    case = container.cases.list_cases()[0]
    output = container.runs.list_runs()[0]
    print(
        json.dumps(
            {
                "mode": "fast-replay",
                "case_id": case.case_id,
                "analysis_run_id": output.analysis_run_id,
                "analysis_status": output.status,
                "pending_proposals": len(container.proposals.list_pending()),
                "next": "POST /api/v1/proposals/{proposal_id}/decisions",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
