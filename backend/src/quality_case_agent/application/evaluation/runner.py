"""Repeatable fixed-seed Agent evaluation runner.

Hidden truth lives in the dataset only. It is used by assertions after the Agent run and is
never placed in the Snapshot, prompt context, tool arguments or Agent output request.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from quality_case_agent.application.case_detection.service import QualityCaseDetectionService
from quality_case_agent.application.ingestion.service import InspectionIngestionService
from quality_case_agent.application.investigation.agent import AgentLimits
from quality_case_agent.application.metrics.worker import MetricsWorker
from quality_case_agent.contracts.evaluation import (
    EvaluationCaseResultContract,
    EvaluationConfigContract,
    EvaluationReportContract,
    EvaluationScenarioContract,
)
from quality_case_agent.domain.quality_case.detector import (
    CaseDetector,
    IlluminationDriftCaseDetector,
    InsufficientEvidenceCaseDetector,
)
from simulator.replay import scenario_replay
from simulator.scenarios import ScenarioName


def _default_dataset_path() -> Path:
    """Resolve the fixed dataset in both source-checkout and installed-container layouts."""

    configured = os.getenv("QUALITY_CASE_EVAL_DATASET")
    candidates = (
        Path(configured) if configured else None,
        Path(__file__).resolve().parents[5] / "evaluation" / "datasets" / "phase13.json",
        Path.cwd() / "evaluation" / "datasets" / "phase13.json",
        Path("/app/evaluation/datasets/phase13.json"),
    )
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate
    locations = ", ".join(str(candidate) for candidate in candidates if candidate is not None)
    raise FileNotFoundError(f"Phase 13 evaluation dataset not found; checked: {locations}")


DATASET_PATH = _default_dataset_path()


@dataclass(frozen=True, slots=True)
class EvaluationDataset:
    version: str
    scenarios: tuple[EvaluationScenarioContract, ...]

    @classmethod
    def load(cls, path: Path = DATASET_PATH) -> EvaluationDataset:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            version=str(raw["dataset_version"]),
            scenarios=tuple(EvaluationScenarioContract.model_validate(item) for item in raw["scenarios"]),
        )


class EvaluationRunner:
    """Run the same hidden evaluation dataset under one or more configurations."""

    def __init__(self, dataset: EvaluationDataset | None = None) -> None:
        self.dataset = dataset or EvaluationDataset.load()

    def run(
        self,
        config: EvaluationConfigContract,
        *,
        repeat_index: int = 1,
    ) -> EvaluationReportContract:
        results = tuple(self._run_case(case, config, repeat_index) for case in self.dataset.scenarios)
        passed = sum(1 for result in results if result.passed)
        return EvaluationReportContract(
            report_id=self._report_id(config, repeat_index),
            dataset_version=self.dataset.version,
            repeat_index=repeat_index,
            config=config,
            cases=list(results),
            summary={
                "case_count": len(results),
                "passed_case_count": passed,
                "pass_rate": round(passed / len(results), 4) if results else 0.0,
                "avg_latency_ms": round(sum(item.latency_ms for item in results) / len(results), 2),
                "avg_tool_call_count": round(sum(item.tool_call_count for item in results) / len(results), 2),
                "avg_estimated_cost_cny": round(
                    sum(item.estimated_cost_cny for item in results) / len(results), 6
                ),
                "evidence_reference_coverage": round(
                    sum(item.evidence_reference_coverage for item in results) / len(results), 4
                ),
                "safety_stop_rate": round(
                    sum(1 for item in results if item.safety_stop_correct) / len(results), 4
                ),
            },
        )

    def run_matrix(
        self,
        configs: tuple[EvaluationConfigContract, ...],
        *,
        repeat_index: int = 1,
    ) -> tuple[EvaluationReportContract, ...]:
        if len(configs) < 2:
            raise ValueError("Task 13 requires at least two configurations for comparison")
        return tuple(self.run(config, repeat_index=repeat_index) for config in configs)

    @staticmethod
    def export(reports: tuple[EvaluationReportContract, ...], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([report.model_dump(mode="json") for report in reports], ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )

    def _run_case(
        self,
        case: EvaluationScenarioContract,
        config: EvaluationConfigContract,
        repeat_index: int,
    ) -> EvaluationCaseResultContract:
        started = perf_counter()
        # Importing the composition root lazily avoids a module cycle when the API registers
        # evaluation routes. Each case receives a fresh container and therefore no hidden state.
        from quality_case_agent.entrypoints.api.app import build_demo_container

        container = build_demo_container(
            agent_limits=AgentLimits(max_iterations=config.max_iterations)
        )
        scenario = ScenarioName(case.scenario)
        detector: CaseDetector | None = None
        if scenario is ScenarioName.ILLUMINATION_DRIFT:
            detector = IlluminationDriftCaseDetector()
        elif scenario is ScenarioName.INSUFFICIENT_EVIDENCE:
            detector = InsufficientEvidenceCaseDetector()
        replay_id = f"eval-{config.config_id}-{case.scenario_id}-{repeat_index}"
        for batch in scenario_replay(scenario, seed=case.seed, batch_size=10, replay_id=replay_id):
            InspectionIngestionService(container.inspection).submit_batch(batch)
        MetricsWorker(container.inspection, container.metrics).run(window_minutes=(1, 5))
        detection = QualityCaseDetectionService(container.metrics, container.cases, detector=detector).run()
        opened = next(iter(detection.opened_cases), None)
        if opened is None:
            raise RuntimeError(f"evaluation scenario did not open a Case: {case.scenario_id}")
        opened_event = next(event for event in detection.events if event.case_id == opened.case_id)
        run_started = perf_counter()
        # The hidden_truth object is deliberately not passed to this call.
        output = container.investigations.handle_case_opened(opened_event)
        analysis_latency = int((perf_counter() - run_started) * 1000)
        total_latency = int((perf_counter() - started) * 1000)
        output = output.model_validate(output.model_dump(mode="json"))
        tool_calls = [event for event in output.trace.events if event.event_type == "TOOL_CALL"]
        actions = {event.action for event in tool_calls}
        required_coverage = len(actions.intersection(case.required_tools)) / len(case.required_tools)
        evidence = output.analysis.evidence
        reference_coverage = sum(bool(item.reference and item.claim) for item in evidence) / len(evidence) if evidence else 0.0
        applicability = sum(item.applicability != "NOT_APPLICABLE" for item in evidence) / len(evidence) if evidence else 1.0
        safety_stop_correct = output.analysis.status == case.expected_status
        violations = 0
        reasons: list[str] = []
        if not safety_stop_correct:
            reasons.append(f"status expected {case.expected_status}, got {output.analysis.status}")
        if case.expected_hypothesis_id and not any(
            item.hypothesis_id == case.expected_hypothesis_id for item in output.analysis.hypotheses
        ):
            reasons.append(f"missing expected hypothesis {case.expected_hypothesis_id}")
        if case.forbid_hypotheses and (output.analysis.hypotheses or output.proposal is not None):
            violations += 1
            reasons.append("insufficient-evidence scenario produced a conclusion or Proposal")
        for required in case.expected_required_information:
            if required not in output.analysis.required_information:
                reasons.append(f"missing required information: {required}")
        if required_coverage < 1.0:
            reasons.append("required tool coverage below 100%")
        tool_summary_tokens = max(1, sum(len(event.summary) for event in output.trace.events) // 4)
        fingerprint_payload = {
            "scenario_id": case.scenario_id,
            "config_id": config.config_id,
            "status": output.analysis.status,
            "hypotheses": [item.hypothesis_id for item in output.analysis.hypotheses],
            "proposal": output.proposal is not None,
            "tools": sorted(actions),
            "evidence": [(item.evidence_class, item.evidence_type, item.applicability) for item in evidence],
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return EvaluationCaseResultContract(
            scenario_id=case.scenario_id,
            config_id=config.config_id,
            dataset_version=self.dataset.version,
            run_fingerprint=fingerprint,
            status=output.analysis.status,
            passed=not reasons,
            schema_valid=True,
            required_tool_coverage=round(required_coverage, 4),
            evidence_reference_coverage=round(reference_coverage, 4),
            applicability_accuracy=round(applicability, 4),
            safety_stop_correct=safety_stop_correct,
            forbidden_conclusion_violations=violations,
            tool_call_count=len(tool_calls),
            retrieval_call_count=sum(1 for event in tool_calls if event.action == "search_knowledge_base"),
            estimated_tokens=tool_summary_tokens,
            estimated_cost_cny=round(tool_summary_tokens * 0.00001, 6),
            latency_ms=total_latency,
            time_to_first_analysis_ms=analysis_latency,
            failure_reasons=reasons,
        )

    @staticmethod
    def _report_id(config: EvaluationConfigContract, repeat_index: int) -> str:
        value = hashlib.sha256(f"{config.config_id}:{config.prompt_version}:{repeat_index}".encode()).hexdigest()[:16]
        return f"eval-{value}"
