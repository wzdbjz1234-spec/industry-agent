"""Generate contract artifacts from the Pydantic source models."""

from __future__ import annotations

import json
from pathlib import Path

from quality_case_agent.contracts.approval import ApprovalEventContract, ProposalDecisionContract
from quality_case_agent.contracts.evaluation import (
    EvaluationCaseResultContract,
    EvaluationConfigContract,
    EvaluationReportContract,
    EvaluationScenarioContract,
    ROICalculationContract,
    ROICalculationRequestContract,
)
from quality_case_agent.contracts.inspection import InspectionResultBatchContract
from quality_case_agent.contracts.investigation import (
    AnalysisCompletedEventContract,
    AnalysisFailedEventContract,
    AnalysisStartedEventContract,
    InvestigationProposedEventContract,
)
from quality_case_agent.contracts.knowledge import (
    CaseArchivedEventContract,
    KnowledgeDocumentContract,
    KnowledgeDocumentUploadContract,
    KnowledgeSearchHitContract,
)
from quality_case_agent.contracts.qms import (
    CaseConfirmedEventContract,
    QmsCreateTaskRequestContract,
    QmsTaskContract,
    QmsTaskCreatedEventContract,
    QmsTaskResultContract,
)
from quality_case_agent.contracts.quality_case import QualityCaseOpenedEventContract
from quality_case_agent.contracts.vision import (
    AnomlibDetectionRequestContract,
    NgRateFluctuationEventContract,
    VisionFaultEventContract,
    VisionFrameRequestContract,
    VisionJobContract,
    VisionStatusContract,
)

from simulator.scenarios import ScenarioName, generate_scenario_batches

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    schema_path = ROOT / "contracts/json-schema/inspection.result.batch.v1.json"
    example_path = ROOT / "contracts/examples/inspection.result.batch.v1.json"
    schema = InspectionResultBatchContract.model_json_schema()
    example = generate_scenario_batches(ScenarioName.NORMAL, seed=7, batch_size=10)[0]
    schema_path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    example_path.write_text(
        json.dumps(example.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    models = {
        "evaluation.config.v1": EvaluationConfigContract,
        "evaluation.scenario.v1": EvaluationScenarioContract,
        "evaluation.case-result.v1": EvaluationCaseResultContract,
        "evaluation.report.v1": EvaluationReportContract,
        "roi.calculation-request.v1": ROICalculationRequestContract,
        "roi.calculation.v1": ROICalculationContract,
        "knowledge.document.v1": KnowledgeDocumentContract,
        "knowledge.document.upload.v1": KnowledgeDocumentUploadContract,
        "knowledge.search-hit.v1": KnowledgeSearchHitContract,
        "quality.case.opened.v1": QualityCaseOpenedEventContract,
        "quality.analysis.started.v1": AnalysisStartedEventContract,
        "quality.analysis.completed.v1": AnalysisCompletedEventContract,
        "quality.analysis.failed.v1": AnalysisFailedEventContract,
        "quality.investigation.proposed.v1": InvestigationProposedEventContract,
        "quality.investigation.decision.v1": ProposalDecisionContract,
        "quality.investigation.approval-event.v1": ApprovalEventContract,
        "qms.task.create-request.v1": QmsCreateTaskRequestContract,
        "qms.task.v1": QmsTaskContract,
        "qms.task.created.v1": QmsTaskCreatedEventContract,
        "qms.task.result-submitted.v1": QmsTaskResultContract,
        "quality.case.confirmed.v1": CaseConfirmedEventContract,
        "quality.case.archived.v1": CaseArchivedEventContract,
        "quality.vision.frame-request.v1": VisionFrameRequestContract,
        "quality.vision.anomlib-detection.v1": AnomlibDetectionRequestContract,
        "quality.vision.job.v1": VisionJobContract,
        "quality.vision.status.v1": VisionStatusContract,
        "quality.vision.fault.v1": VisionFaultEventContract,
        "quality.vision.ng-rate-fluctuation.v1": NgRateFluctuationEventContract,
    }
    for name, model in models.items():
        path = ROOT / "contracts/json-schema" / f"{name}.json"
        path.write_text(json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Generated {path.relative_to(ROOT)}")
    baseline_config = EvaluationConfigContract(
        config_id="baseline",
        model="deterministic-investigation-1",
        prompt_version="prompt-v1",
        tool_version="readonly-tools-v2",
    )
    example_case = EvaluationCaseResultContract(
        scenario_id="fixture-offset-001",
        config_id="baseline",
        dataset_version="phase13-v1",
        run_fingerprint="sha256:example",
        status="COMPLETED",
        passed=True,
        schema_valid=True,
        required_tool_coverage=1.0,
        evidence_reference_coverage=1.0,
        applicability_accuracy=1.0,
        safety_stop_correct=True,
        tool_call_count=4,
        retrieval_call_count=1,
        estimated_tokens=120,
        estimated_cost_cny=0.0012,
        latency_ms=10,
        time_to_first_analysis_ms=9,
    )
    examples = {
        "evaluation.config.v1": baseline_config,
        "evaluation.scenario.v1": EvaluationScenarioContract(
            scenario_id="fixture-offset-001",
            dataset_version="phase13-v1",
            scenario="fixture_offset",
            seed=7,
            required_tools=["get_case_snapshot"],
            expected_status="COMPLETED",
        ),
        "evaluation.case-result.v1": example_case,
        "evaluation.report.v1": EvaluationReportContract(
            report_id="eval-example",
            dataset_version="phase13-v1",
            repeat_index=1,
            config=baseline_config,
            cases=[example_case],
            summary={"case_count": 1, "pass_rate": 1.0},
        ),
        "roi.calculation-request.v1": ROICalculationRequestContract(),
        "roi.calculation.v1": ROICalculationContract(
            annual_cases=2000,
            annual_labor_hours_saved=733.33,
            annual_benefit_cny=110000,
            annual_cost_cny=21600,
            annual_net_benefit_cny=88400,
            roi_percent=-26.33,
            payback_months=16.29,
            assumptions={"cases_per_day": 8.0},
        ),
        "quality.vision.frame-request.v1": VisionFrameRequestContract(
            frame_id="frame-0001",
            inspected_at="2026-08-23T10:00:00Z",
            factory_id="factory-01",
            line_id="line-01",
            station_id="camera-01",
            product_id="part-A",
            unit_id="unit-0001",
            batch_id="batch-20260823-01",
            image_path="/data/incoming/frame-0001.png",
        ),
        "quality.vision.anomlib-detection.v1": AnomlibDetectionRequestContract(
            frame_id="frame-0001",
            inspected_at="2026-08-23T10:00:00Z",
            factory_id="factory-01",
            line_id="line-01",
            station_id="camera-01",
            product_id="part-A",
            unit_id="unit-0001",
            batch_id="batch-20260823-01",
            detector_version="anomlib-demo-1",
            anomaly_score=0.87,
            threshold=0.2,
            is_ng=True,
            defect_type="surface_defect",
        ),
        "quality.vision.job.v1": VisionJobContract(
            job_id="vision-job-0001",
            frame_id="frame-0001",
            scheme="efficientad",
            status="COMPLETED",
            submitted_at="2026-08-23T10:00:00Z",
            completed_at="2026-08-23T10:00:01Z",
            result_id="inspection-batch-0001",
            is_ng=True,
            anomaly_score=0.87,
        ),
        "quality.vision.status.v1": VisionStatusContract(
            running=True,
            queued=2,
            completed=128,
            failed=1,
            registered_schemes=["efficientad", "anomlib"],
        ),
        "quality.vision.fault.v1": VisionFaultEventContract(
            event_id="vision-fault-0001",
            occurred_at="2026-08-23T10:00:01Z",
            trace_id="trace-0001",
            frame_id="frame-0001",
            scope={"factory_id": "factory-01", "station_id": "camera-01"},
            fault_kind="NG_DETECTION",
            detector_type="efficientad",
            model_version="provided-30-111",
            anomaly_score=0.87,
            threshold=0.2,
            details={"defect_type": "surface_defect"},
        ),
        "quality.vision.ng-rate-fluctuation.v1": NgRateFluctuationEventContract(
            event_id="ng-fluctuation:scope-hash:trace-0001:RISING",
            occurred_at="2026-08-23T10:00:20Z",
            trace_id="trace-0001",
            scope={"factory_id": "factory-01", "line_id": "line-01", "station_id": "camera-01"},
            window_start="2026-08-23T10:00:01Z",
            window_end="2026-08-23T10:00:20Z",
            sample_count=20,
            baseline_ng_rate=0.1,
            recent_ng_rate=0.5,
            delta=0.4,
            direction="RISING",
            details={"window_size": 20, "minimum_samples": 6},
        ),
    }
    for name, example_model in examples.items():
        path = ROOT / "contracts/examples" / f"{name}.json"
        path.write_text(
            json.dumps(example_model.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Generated {path.relative_to(ROOT)}")
    print(f"Generated {schema_path.relative_to(ROOT)}")
    print(f"Generated {example_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
