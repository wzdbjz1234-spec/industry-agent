# Repository Guidelines

## Project Structure & Module Organization

The repository was originally design-first. Existing Markdown files still document the implemented Quality Case/QMS baseline, but new product-simplification work must treat `quality_investigation_copilot_development_plan.md` as the execution source of truth. Use `quality_case_investigation_agent_design.md`, `quality_case_agent_development_plan.md`, and `quality_case_agent_optimization_roadmap.md` as historical architecture and migration context; do not extend the legacy Proposal/QMS main flow unless the new plan explicitly calls for it.

`efficientad-package/` is the existing detector package. Its source lives under `efficientad-package/src/efficientad/`, tests belong in `efficientad-package/tests/`, and model/data artifacts are under `output/`, `data/`, `templates/`, and `resources/`. The planned application will add `backend/`, `web/`, `simulator/`, `contracts/`, and `docs/`; follow the package boundaries documented in the development plan.

## Build, Test, and Development Commands

Run current Python commands from `efficientad-package/`:

```powershell
pip install -e .       # install the detector package for development
pytest                 # run tests configured under tests/
python run_ui.py       # launch the local detector GUI
efficientad-train --help
```

Do not document planned root commands as working until their configuration exists. When the application skeleton lands, prefer reproducible `uv` and Docker Compose commands committed to the root README.

## Coding Style & Naming Conventions

Use four spaces in Python, type annotations on public interfaces, `snake_case` for modules/functions, and `PascalCase` for classes and Pydantic models. Keep domain code independent of FastAPI, SQLAlchemy, Redis, and model-provider SDKs. Version external messages, for example `quality.case.opened.v1`, and validate them at entry points. Use Ruff and mypy once configured; avoid editing generated schemas or frontend API types manually.

## Testing Guidelines

Use pytest with files named `test_*.py`. Add unit tests for domain rules, integration tests for PostgreSQL/Redis/MinIO boundaries, contract tests for every message example, and Playwright tests for critical WebUI flows. Every bug fix should include a regression test. Preserve fixed seeds for simulator and Agent-evaluation scenarios.

## Commit & Pull Request Guidelines

No Git history is present, so no existing convention can be inferred. Use Conventional Commits such as `feat(case): create immutable snapshot` or `test(events): cover duplicate delivery`. Keep commits scoped to one vertical task. PRs should include purpose, linked task, protocol or migration impact, test commands/results, and screenshots for UI changes.

## Security & Configuration

Never commit secrets, private production documents, or new proprietary datasets/model outputs. Use `.env.example` for configuration, signed QMS webhooks, and synthetic or public demo data. Agents may propose actions but must not bypass human approval or call QMS write operations directly.
