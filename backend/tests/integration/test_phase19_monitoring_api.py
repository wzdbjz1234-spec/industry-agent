"""Phase 19 monitoring API contract tests."""

import asyncio

from httpx import ASGITransport, AsyncClient
from quality_case_agent.entrypoints.api.app import create_app


def test_monitoring_endpoints_return_versioned_contracts() -> None:
    async def run() -> None:
        async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as client:
            seeded = await client.post("/api/v1/demo/fixture-offset")
            assert seeded.status_code == 200
            baseline = await client.post("/api/v1/monitoring/baseline")
            assert baseline.status_code == 200
            assert baseline.json()["baseline_count"] >= 1
            health = await client.get("/api/v1/monitoring/health")
            assert health.status_code == 200
            body = health.json()
            assert body["schema_version"] == "1.0"
            assert body["window_count"] >= 1
            assert isinstance(body["decisions"], list)

    asyncio.run(run())
