"""Phase 12 API projections expose structured operations data only."""

import asyncio

import httpx
from quality_case_agent.entrypoints.api.app import create_app


def test_operations_api_exposes_timeline_worker_and_analysis_metrics() -> None:
    async def exercise() -> None:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            seeded = await client.post("/api/v1/demo/illumination-drift")
            assert seeded.status_code == 200
            case_id = seeded.json()["case_ids"][0]

            timeline = await client.get(f"/api/v1/cases/{case_id}/timeline")
            assert timeline.status_code == 200
            event_types = [item["event_type"] for item in timeline.json()]
            assert "quality.case.opened.v1" in event_types
            assert "quality.analysis.started.v1" in event_types
            assert "quality.analysis.completed.v1" in event_types
            assert all("chain" not in item["summary"].lower() for item in timeline.json())

            workers = await client.get("/api/v1/operations/workers")
            assert workers.status_code == 200
            worker_names = {item["worker"] for item in workers.json()["workers"]}
            assert "investigation-worker" in worker_names

            metrics = await client.get("/api/v1/operations/analysis-metrics")
            assert metrics.status_code == 200
            assert metrics.json()[0]["retrieval_call_count"] >= 1
            assert metrics.json()[0]["estimated_tokens"] > 0

    asyncio.run(exercise())
