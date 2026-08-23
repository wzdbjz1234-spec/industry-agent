"""Guard the frozen repository/package boundaries until implementation lands."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


REQUIRED_DIRECTORIES = (
    "backend/src/quality_case_agent/contracts",
    "backend/src/quality_case_agent/domain/inspection",
    "backend/src/quality_case_agent/domain/quality_case",
    "backend/src/quality_case_agent/domain/investigation",
    "backend/src/quality_case_agent/domain/knowledge",
    "backend/src/quality_case_agent/application/ingestion",
    "backend/src/quality_case_agent/application/metrics",
    "backend/src/quality_case_agent/application/case_detection",
    "backend/src/quality_case_agent/application/investigation",
    "backend/src/quality_case_agent/application/approval",
    "backend/src/quality_case_agent/application/archival",
    "backend/src/quality_case_agent/application/ports",
    "backend/src/quality_case_agent/adapters/postgres",
    "backend/src/quality_case_agent/adapters/redis_streams",
    "backend/src/quality_case_agent/adapters/minio",
    "backend/src/quality_case_agent/adapters/pgvector",
    "backend/src/quality_case_agent/adapters/llm",
    "backend/src/quality_case_agent/adapters/embeddings",
    "backend/src/quality_case_agent/adapters/detector",
    "backend/src/quality_case_agent/adapters/qms",
    "backend/src/quality_case_agent/entrypoints/api",
    "backend/src/quality_case_agent/entrypoints/mock_qms",
    "backend/src/quality_case_agent/entrypoints/workers",
    "backend/src/quality_case_agent/entrypoints/cli",
    "web/src",
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
    "scripts",
)


def test_frozen_directories_exist() -> None:
    missing = [path for path in REQUIRED_DIRECTORIES if not (ROOT / path).is_dir()]
    assert not missing, f"Missing frozen package directories: {missing}"


def test_backend_root_modules_exist() -> None:
    package_root = ROOT / "backend/src/quality_case_agent"
    expected = {"config.py", "logging.py", "bootstrap.py"}
    actual = {path.name for path in package_root.iterdir() if path.is_file()}
    assert expected <= actual
