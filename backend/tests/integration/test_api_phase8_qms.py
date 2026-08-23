"""Phase 8 API-to-Worker-to-QMS smoke tests."""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
from quality_case_agent.entrypoints.api.app import create_app
from quality_case_agent.entrypoints.mock_qms.app import create_mock_qms_app


def test_approval_api_creates_one_qms_task_and_exposes_delivery_state() -> None:
    async def exercise() -> None:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            seeded = await client.post("/api/v1/demo/fixture-offset")
            assert seeded.status_code == 200

            pending = (await client.get("/api/v1/proposals/pending")).json()
            assert len(pending) == 1
            proposal = pending[0]
            decision = {
                "decision_id": "decision-api-phase8-001",
                "proposal_id": proposal["proposal_id"],
                "case_id": proposal["case_id"],
                "decision": "APPROVE",
                "decided_by": "web-demo-user",
                "decided_at": "2026-08-23T10:00:00Z",
            }
            response = await client.post(
                f"/api/v1/proposals/{proposal['proposal_id']}/decisions",
                json=decision,
            )
            assert response.status_code == 200
            assert response.json()["qms_task_event"]["task"]["status"] == "OPEN"

            tasks = await client.get("/api/v1/qms/tasks")
            assert tasks.status_code == 200
            assert len(tasks.json()["items"]) == 1
            assert tasks.json()["items"][0]["case_id"] == proposal["case_id"]

            cases = await client.get("/api/v1/cases")
            assert cases.json()[0]["case_status"] == "QMS_OPEN"
            assert cases.json()[0]["qms_task_id"] == "QMS-TASK-0001"

            replay = await client.post(
                f"/api/v1/proposals/{proposal['proposal_id']}/decisions",
                json=decision,
            )
            assert replay.status_code == 200
            assert replay.json()["qms_task_event"]["task"]["task_id"] == "QMS-TASK-0001"
            delivery = await client.get("/api/v1/qms/delivery")
            assert len(delivery.json()["processed"]) == 1

    asyncio.run(exercise())


def test_standalone_mock_qms_rest_api_manages_tasks() -> None:
    async def exercise() -> None:
        transport = httpx.ASGITransport(app=create_mock_qms_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://qms") as client:
            payload = {
                "proposal_id": "proposal-api-qms-001",
                "case_id": "case-api-qms-001",
                "title": "检查定位销",
                "reason": "确认右上偏移的现场原因",
                "steps": [
                    {
                        "order": 1,
                        "instruction": "测量定位销间隙",
                        "expected_evidence": "测量记录",
                    }
                ],
                "assignee_role": "QUALITY_ENGINEER",
                "priority": "HIGH",
                "risk_level": "MEDIUM",
            }
            created = await client.post("/api/v1/tasks", json=payload)
            assert created.status_code == 200
            task_id = created.json()["task_id"]
            assert created.json()["task_uri"].endswith(task_id)

            by_proposal = await client.get("/api/v1/tasks/by-proposal/proposal-api-qms-001")
            assert by_proposal.json()["task_id"] == task_id
            listed = await client.get("/api/v1/tasks")
            assert len(listed.json()["items"]) == 1
            updated = await client.post(
                f"/api/v1/tasks/{task_id}/status", params={"status": "IN_PROGRESS"}
            )
            assert updated.json()["status"] == "IN_PROGRESS"
            now = datetime.now(UTC)
            result = {
                "event_type": "qms.task.result-submitted.v1",
                "event_id": "qms-result-mock-api-001",
                "occurred_at": now.isoformat(),
                "confirmation_id": "confirmation-mock-api-001",
                "case_id": "case-api-qms-001",
                "task_id": task_id,
                "confirmed_by": "engineer-01",
                "actual_root_cause": {"code": "FIXTURE_PIN", "description": "定位销松动"},
                "actual_actions": ["更换定位销"],
                "verification": {
                    "status": "VERIFIED_EFFECTIVE",
                    "start": (now - timedelta(hours=1)).isoformat(),
                    "end": now.isoformat(),
                    "sample_count": 100,
                    "ng_rate_before": 0.08,
                    "ng_rate_after": 0.01,
                    "acceptance_criteria": "NG率低于2%",
                },
                "agent_assessment": {
                    "top_hypothesis_matched": True,
                    "useful": True,
                    "human_rating": 4,
                },
            }
            submitted = await client.post(f"/api/v1/tasks/{task_id}/result", json=result)
            assert submitted.status_code == 200
            assert submitted.json()["signature"]
            assert (await client.get(f"/api/v1/tasks/{task_id}")).json()["status"] == "CLOSED"
            result_page = await client.get(f"/tasks/{task_id}/result")
            assert "生成签名结果" in result_page.text
            page = await client.get("/")
            assert task_id in page.text

    asyncio.run(exercise())
