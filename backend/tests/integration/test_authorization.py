"""Phase 21 API authorization is enforced at the application entrypoint."""

import asyncio

import httpx
from quality_case_agent.entrypoints.api.app import create_app


def test_viewer_cannot_approve_but_approver_can_and_audit_is_visible() -> None:
    async def exercise() -> None:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/demo/fixture-offset")
            proposal = (await client.get("/api/v1/proposals/pending")).json()[0]
            decision = {
                "decision_id": "phase21-auth-decision",
                "proposal_id": proposal["proposal_id"],
                "case_id": proposal["case_id"],
                "decision": "REJECT",
                "decided_by": "viewer-1",
                "decided_at": "2026-08-25T10:00:00Z",
                "comment": "not approved",
            }
            denied = await client.post(
                f"/api/v1/proposals/{proposal['proposal_id']}/decisions",
                json=decision,
                headers={"X-Actor-Id": "viewer-1", "X-Actor-Role": "VIEWER"},
            )
            assert denied.status_code == 403
            decision["decision_id"] = "phase21-auth-decision-approved"
            decision["decided_by"] = "approver-1"
            accepted = await client.post(
                f"/api/v1/proposals/{proposal['proposal_id']}/decisions",
                json=decision,
                headers={"X-Actor-Id": "approver-1", "X-Actor-Role": "APPROVER"},
            )
            assert accepted.status_code == 200
            audit = await client.get(
                "/api/v1/audit/events",
                headers={"X-Actor-Id": "approver-1", "X-Actor-Role": "APPROVER"},
            )
            assert audit.status_code == 200
            assert any(item["resource_id"] == proposal["proposal_id"] for item in audit.json())

    asyncio.run(exercise())
