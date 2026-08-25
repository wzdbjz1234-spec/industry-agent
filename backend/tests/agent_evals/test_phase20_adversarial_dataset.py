"""Small, deterministic contract for the Phase 20 adversarial eval dataset."""

import json
from pathlib import Path


def test_adversarial_dataset_has_abstention_and_proposal_cases() -> None:
    path = Path("evaluation/datasets/adversarial/phase20_grounding_cases.jsonl")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert {row["expected"] for row in rows} == {"ABSTAIN", "PROPOSE"}
    assert len(rows) >= 4
