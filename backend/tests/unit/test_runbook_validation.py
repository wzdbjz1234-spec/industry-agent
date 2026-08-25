"""Phase 20 Runbook contract and registry safety tests."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from quality_case_agent.application.investigation.runbooks import RunbookRegistry
from quality_case_agent.contracts.runbook import RunbookContract
from quality_case_agent.domain.runbook.validation import to_domain


def test_runbook_contract_is_data_only_and_converts_to_domain() -> None:
    contract = RunbookContract(
        runbook_id="demo",
        version="1.0",
        trigger_family="DEMO",
        required_tools=["get_case_snapshot"],
        knowledge_query="demo query",
        candidate_hypotheses=[
            {
                "hypothesis_id": "H-DEMO",
                "title": "待验证方向",
                "description": "仅用于测试",
                "default_confidence": 0.4,
            }
        ],
    )
    domain = to_domain(contract)
    assert domain.runbook_id == "demo"
    assert domain.candidate_hypotheses[0].hypothesis_id == "H-DEMO"


def test_runbook_rejects_unknown_or_executable_fields() -> None:
    with pytest.raises(ValidationError):
        RunbookContract.model_validate(
            {
                "runbook_id": "unsafe",
                "version": "1.0",
                "trigger_family": "UNSAFE",
                "required_tools": ["python"],
                "knowledge_query": "query",
                "candidate_hypotheses": [],
                "python": "import os",
            }
        )


def test_registry_loads_versioned_json_and_falls_back_to_default() -> None:
    registry = RunbookRegistry.from_directory(
        Path("knowledge_base") / "runbooks"
    )
    assert registry.get("FIXTURE_OFFSET").runbook_id == "fixture-offset-investigation"
    assert registry.get("NEW_TRIGGER").runbook_id == "generic-investigation"
