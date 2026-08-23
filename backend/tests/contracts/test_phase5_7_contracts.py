"""Golden examples for Phase 5–7 event contracts."""

import json
from pathlib import Path

from quality_case_agent.contracts.investigation import (
    AnalysisCompletedEventContract,
    InvestigationProposedEventContract,
)
from quality_case_agent.contracts.qms import QmsTaskCreatedEventContract, QmsTaskResultContract
from quality_case_agent.contracts.quality_case import QualityCaseOpenedEventContract

ROOT = Path(__file__).resolve().parents[3]


def _example(name: str) -> dict[str, object]:
    return json.loads((ROOT / "contracts/examples" / name).read_text(encoding="utf-8"))


def test_phase5_7_golden_events_validate() -> None:
    QualityCaseOpenedEventContract.model_validate(_example("quality.case.opened.v1.json"))
    AnalysisCompletedEventContract.model_validate(
        _example("quality.analysis.completed.v1.json")
    )
    InvestigationProposedEventContract.model_validate(
        _example("quality.investigation.proposed.v1.json")
    )
    QmsTaskCreatedEventContract.model_validate(_example("qms.task.created.v1.json"))
    QmsTaskResultContract.model_validate(_example("qms.task.result-submitted.v1.json"))
