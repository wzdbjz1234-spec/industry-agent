"""Run the Phase 11 illumination-drift and evidence-safety demos."""

from __future__ import annotations

import json

from quality_case_agent.application.case_detection.service import QualityCaseDetectionService
from quality_case_agent.application.ingestion.service import InspectionIngestionService
from quality_case_agent.application.metrics.worker import MetricsWorker
from quality_case_agent.domain.quality_case.detector import (
    IlluminationDriftCaseDetector,
    InsufficientEvidenceCaseDetector,
)
from quality_case_agent.entrypoints.api.app import build_demo_container

from simulator.replay import scenario_replay
from simulator.scenarios import ScenarioName


def _run(container, scenario: ScenarioName, detector, replay_id: str) -> dict[str, object]:
    for batch in scenario_replay(scenario, seed=7, batch_size=10, replay_id=replay_id):
        InspectionIngestionService(container.inspection).submit_batch(batch)
    MetricsWorker(container.inspection, container.metrics).run(window_minutes=(1, 5))
    detection = QualityCaseDetectionService(
        container.metrics, container.cases, detector=detector
    ).run()
    for event in detection.events:
        if event.event_type == "quality.case.opened.v1":
            container.investigations.handle_case_opened(event)
    case = detection.opened_cases[0]
    output = container.runs.get_output(
        next(
            run.analysis_run_id
            for run in container.runs.list_runs()
            if run.case_id == case.case_id
        )
    )
    if output is None:
        raise RuntimeError(f"Phase 11 analysis missing for {case.case_id}")
    return {
        "scenario": scenario.value,
        "case_id": case.case_id,
        "trigger_family": case.trigger_family,
        "analysis_status": output.analysis.status,
        "summary": output.analysis.summary,
        "hypotheses": [item.title for item in output.analysis.hypotheses],
        "proposal": output.proposal.title if output.proposal else None,
        "required_information": output.analysis.required_information,
        "termination_reason": output.analysis.termination_reason,
    }


def main() -> int:
    container = build_demo_container()
    results = [
        _run(
            container,
            ScenarioName.ILLUMINATION_DRIFT,
            IlluminationDriftCaseDetector(),
            "phase11-illumination",
        ),
        _run(
            container,
            ScenarioName.INSUFFICIENT_EVIDENCE,
            InsufficientEvidenceCaseDetector(),
            "phase11-insufficient",
        ),
    ]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
