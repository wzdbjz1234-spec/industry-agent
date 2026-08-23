"""FastAPI entrypoint smoke test for the local Phase 5–7 demo."""

import asyncio

import httpx
from quality_case_agent.entrypoints.api.app import create_app


def test_api_drives_fixture_demo_and_search() -> None:
    async def exercise() -> None:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/demo/fixture-offset")
            assert response.status_code == 200
            assert response.json()["case_ids"]

            response = await client.get("/api/v1/analysis/runs")
            assert response.status_code == 200
            assert len(response.json()) == 1

            response = await client.get(
                "/api/v1/knowledge/search",
                params={
                    "query": "fixture positioning pin",
                    "station_id": "camera-01",
                    "product_id": "part-A",
                },
            )
            assert response.status_code == 200
            assert response.json()[0]["document_id"] == "fixture-manual-v4"

    asyncio.run(exercise())
