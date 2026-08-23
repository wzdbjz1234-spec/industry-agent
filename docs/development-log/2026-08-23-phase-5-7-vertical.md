# 2026-08-23：Phase 5–7 vertical slice

## 完成范围

- Markdown/PDF parser port and upload metadata contract;
- content hash idempotency, ACTIVE/SUPERSEDED and effective/applicability filtering;
- deterministic Embedding Provider, local hybrid retrieval and a pgvector SQL repository seam;
- representative sample read-only tool;
- durable Analysis Run checkpoint, trace output and analysis lifecycle events;
- automatic Case-opened handling with `case_id + snapshot_id + trigger_event_id` idempotency;
- proposal-created event, pending proposal query, approval audit/versioning and reanalysis callback;
- FastAPI local entrypoint and deterministic API composition root;
- synthetic fixture/illumination manuals and one verified historical case.

## 离线演示

```powershell
uv run python scripts/run_phase5_7_demo.py
uv run uvicorn quality_case_agent.entrypoints.api.app:app --reload
```

The demo proves that replaying the same Case-opened event creates one Analysis Run and one Proposal,
while a human decision creates a new run only for `REQUEST_REANALYSIS`.

## 留待后续基础设施任务

The repository keeps PostgreSQL/pgvector, Redis Streams, MinIO and real provider adapters behind
ports. Their network-backed implementations, migrations, SSE transport and React/Playwright shell
remain later infrastructure work; the offline path is the acceptance test double.
