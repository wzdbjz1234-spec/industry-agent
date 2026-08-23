"""Task 13 deterministic evaluation and illustrative ROI tests."""

from pathlib import Path

from quality_case_agent.application.evaluation.roi import calculate_roi
from quality_case_agent.application.evaluation.runner import EvaluationDataset, EvaluationRunner
from quality_case_agent.contracts.evaluation import (
    EvaluationConfigContract,
    ROICalculationRequestContract,
)


def _config(config_id: str, prompt_version: str) -> EvaluationConfigContract:
    return EvaluationConfigContract(
        config_id=config_id,
        model="deterministic-investigation-1",
        prompt_version=prompt_version,
        tool_version="readonly-tools-v2",
        max_iterations=8,
    )


def test_eval_fixed_seed_is_reproducible_and_keeps_hidden_truth_out_of_output() -> None:
    runner = EvaluationRunner()
    first = runner.run(_config("baseline", "prompt-v1"))
    second = runner.run(_config("baseline", "prompt-v1"))
    assert first.dataset_version == "phase13-v1"
    assert [item.run_fingerprint for item in first.cases] == [
        item.run_fingerprint for item in second.cases
    ]
    assert all(item.passed for item in first.cases)
    insufficient = next(item for item in first.cases if "insufficient" in item.scenario_id)
    assert insufficient.safety_stop_correct is True
    assert insufficient.forbidden_conclusion_violations == 0
    assert insufficient.status == "INSUFFICIENT_EVIDENCE"


def test_eval_matrix_compares_two_prompt_configurations() -> None:
    reports = EvaluationRunner().run_matrix(
        (_config("baseline", "prompt-v1"), _config("safe-v2", "prompt-v2"))
    )
    assert len(reports) == 2
    assert {report.config.prompt_version for report in reports} == {"prompt-v1", "prompt-v2"}
    assert all(report.summary["case_count"] == 3 for report in reports)


def test_eval_dataset_path_is_available_from_repository_layout() -> None:
    assert EvaluationDataset.load(Path("evaluation/datasets/phase13.json")).version == "phase13-v1"


def test_roi_is_explicitly_illustrative_and_parameterized() -> None:
    result = calculate_roi(ROICalculationRequestContract())
    assert result.classification == "ILLUSTRATIVE"
    assert "示例测算" in result.disclaimer
    assert result.annual_labor_hours_saved > 0
    assert result.annual_benefit_cny > result.annual_cost_cny
