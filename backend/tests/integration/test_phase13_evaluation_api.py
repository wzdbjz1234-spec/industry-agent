"""Task 13 API and health endpoint acceptance tests."""

import asyncio

import httpx
from quality_case_agent.entrypoints.api.app import create_app


def test_health_eval_matrix_and_roi_api() -> None:
    async def exercise() -> None:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/health")
            assert health.status_code == 200
            assert health.json()["status"] == "ok"

            dataset = await client.get("/api/v1/evaluation/dataset")
            assert dataset.status_code == 200
            assert len(dataset.json()["scenarios"]) == 3
            assert all("hidden_truth" not in item for item in dataset.json()["scenarios"])

            reports = await client.post(
                "/api/v1/evaluation/matrix",
                json=[
                    {
                        "config_id": "baseline",
                        "model": "deterministic-investigation-1",
                        "prompt_version": "prompt-v1",
                        "tool_version": "readonly-tools-v2",
                    },
                    {
                        "config_id": "safe-v2",
                        "model": "deterministic-investigation-1",
                        "prompt_version": "prompt-v2",
                        "tool_version": "readonly-tools-v2",
                    },
                ],
            )
            assert reports.status_code == 200
            assert len(reports.json()) == 2
            assert all(report["summary"]["pass_rate"] == 1.0 for report in reports.json())

            roi = await client.post("/api/v1/roi/calculate", json={"cases_per_day": 10})
            assert roi.status_code == 200
            assert roi.json()["classification"] == "ILLUSTRATIVE"
            assert "示例测算" in roi.json()["disclaimer"]

    asyncio.run(exercise())
