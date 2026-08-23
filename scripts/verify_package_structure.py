"""Verify the Phase 1 repository/package structure without importing runtime dependencies."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DIRECTORIES = (
    "backend/src/quality_case_agent/contracts",
    "backend/src/quality_case_agent/domain",
    "backend/src/quality_case_agent/application",
    "backend/src/quality_case_agent/adapters",
    "backend/src/quality_case_agent/entrypoints",
    "backend/tests/unit",
    "backend/tests/integration",
    "backend/tests/contracts",
    "backend/tests/agent_evals",
    "web/src/generated",
    "simulator/scenarios",
    "knowledge_base",
    "contracts/json-schema",
    "contracts/examples",
    "contracts/asyncapi",
    "docs/architecture",
    "docs/adr",
    "docs/development-log",
    "docs/demo",
    "docs/evaluation",
)


def main() -> int:
    missing = [path for path in REQUIRED_DIRECTORIES if not (ROOT / path).is_dir()]
    if missing:
        print("Missing package directories:")
        for path in missing:
            print(f"- {path}")
        return 1

    print(f"Package structure OK ({len(REQUIRED_DIRECTORIES)} directories checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
