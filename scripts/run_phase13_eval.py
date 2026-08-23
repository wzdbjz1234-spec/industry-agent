"""Run the three-scenario Agent Eval matrix and export a JSON report."""

from __future__ import annotations

import json
from pathlib import Path

from quality_case_agent.application.evaluation.runner import EvaluationRunner
from quality_case_agent.contracts.evaluation import EvaluationConfigContract

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    runner = EvaluationRunner()
    configs = (
        EvaluationConfigContract(
            config_id="baseline",
            model="deterministic-investigation-1",
            prompt_version="prompt-v1",
            tool_version="readonly-tools-v2",
        ),
        EvaluationConfigContract(
            config_id="safe-v2",
            model="deterministic-investigation-1",
            prompt_version="prompt-v2",
            tool_version="readonly-tools-v2",
        ),
    )
    reports = runner.run_matrix(configs)
    output_path = ROOT / "artifacts" / "evaluation" / "phase13-report.json"
    runner.export(reports, output_path)
    print(
        json.dumps(
            {
                "output": str(output_path.relative_to(ROOT)),
                "dataset_version": runner.dataset.version,
                "reports": [
                    {
                        "config_id": report.config.config_id,
                        "prompt_version": report.config.prompt_version,
                        "summary": report.summary,
                        "cases": [
                            {
                                "scenario_id": case.scenario_id,
                                "passed": case.passed,
                                "status": case.status,
                                "failure_reasons": case.failure_reasons,
                            }
                            for case in report.cases
                        ],
                    }
                    for report in reports
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
