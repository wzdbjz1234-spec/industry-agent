"""Golden contract tests for inspection.result.batch.v1."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from quality_case_agent.contracts.inspection import InspectionResultBatchContract

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "contracts/examples/inspection.result.batch.v1.json"


def test_golden_example_is_valid() -> None:
    batch = InspectionResultBatchContract.model_validate_json(EXAMPLE.read_text(encoding="utf-8"))
    assert batch.schema_version == "1.0"
    assert len(batch.records) == 10
    assert batch.produced_at.tzinfo is not None


def test_batch_rejects_duplicate_result_ids() -> None:
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["records"][1]["result_id"] = payload["records"][0]["result_id"]
    with pytest.raises(ValidationError, match="result_id must be unique"):
        InspectionResultBatchContract.model_validate(payload)


def test_batch_rejects_naive_timestamps() -> None:
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["produced_at"] = "2026-08-22T02:00:00"
    with pytest.raises(ValidationError, match="timestamps must include a timezone"):
        InspectionResultBatchContract.model_validate(payload)
