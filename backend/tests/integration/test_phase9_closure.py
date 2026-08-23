"""Phase 9 signed QMS result -> confirmation -> archive -> case library tests."""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from quality_case_agent.adapters.in_memory.stores import InMemoryQualityCaseStore
from quality_case_agent.application.qms.service import QmsWebhookService, sign_qms_result
from quality_case_agent.contracts.qms import (
    ActualRootCauseContract,
    AgentAssessmentContract,
    QmsTaskResultContract,
    VerificationContract,
)
from quality_case_agent.entrypoints.api.app import create_app


def _result(case_id: str, task_id: str, *, status: str = "VERIFIED_EFFECTIVE") -> QmsTaskResultContract:
    now = datetime.now(UTC)
    return QmsTaskResultContract(
        event_id=f"qms-result-phase9-{status.lower()}",
        occurred_at=now,
        confirmation_id=f"confirmation-phase9-{status.lower()}",
        case_id=case_id,
        task_id=task_id,
        confirmed_by="engineer-phase9",
        actual_root_cause=ActualRootCauseContract(
            code="FIXTURE_LOCATING_PIN_LOOSE", description="定位销松动导致右上偏移"
        ),
        actual_actions=["更换定位销"],
        verification=VerificationContract(
            status=status,  # type: ignore[arg-type]
            start=now - timedelta(hours=1),
            end=now,
            sample_count=500,
            ng_rate_before=0.087,
            ng_rate_after=0.018,
            acceptance_criteria="连续500件NG率低于2%",
        ),
        agent_assessment=AgentAssessmentContract(
            top_hypothesis_matched=True,
            useful=True,
            human_rating=4,
            comment="现场结果已回传",
        ),
    )


def test_api_closes_case_archives_full_payload_and_promotes_verified_case() -> None:
    async def exercise() -> None:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/demo/fixture-offset")
            proposal = (await client.get("/api/v1/proposals/pending")).json()[0]
            decision = {
                "decision_id": "decision-phase9-api-001",
                "proposal_id": proposal["proposal_id"],
                "case_id": proposal["case_id"],
                "decision": "APPROVE",
                "decided_by": "engineer-phase9",
                "decided_at": datetime.now(UTC).isoformat(),
            }
            await client.post(
                f"/api/v1/proposals/{proposal['proposal_id']}/decisions", json=decision
            )
            task = (await client.get("/api/v1/qms/tasks")).json()["items"][0]
            result = _result(proposal["case_id"], task["task_id"])
            signature = sign_qms_result(result, b"phase9-demo-secret")
            response = await client.post(
                "/api/v1/integrations/qms/task-results",
                json=result.model_dump(mode="json"),
                headers={"X-QMS-Signature": signature},
            )
            assert response.status_code == 200
            assert response.json()["archive_event"]["knowledge_index_status"] == "INDEXED"

            case = (await client.get(f"/api/v1/cases/{proposal['case_id']}")).json()
            assert case["case_status"] == "ARCHIVED"
            archive = (await client.get(f"/api/v1/cases/{proposal['case_id']}/archive")).json()
            assert {"snapshot", "investigation", "approval", "qms_task", "human_confirmation"} <= set(archive)
            assert archive["integrity"]["content_hash"].startswith("sha256:")
            assert len((await client.get("/api/v1/case-library")).json()) == 1

            replay = await client.post(
                "/api/v1/integrations/qms/task-results",
                json=result.model_dump(mode="json"),
                headers={"X-QMS-Signature": signature},
            )
            assert replay.status_code == 200
            assert replay.json()["archive_event"] == response.json()["archive_event"]

            revision = result.model_copy(
                update={
                    "event_id": "qms-result-phase9-revision-002",
                    "confirmation_id": "confirmation-phase9-revision-002",
                }
            )
            revision_response = await client.post(
                "/api/v1/integrations/qms/task-results",
                json=revision.model_dump(mode="json"),
                headers={"X-QMS-Signature": sign_qms_result(revision, b"phase9-demo-secret")},
            )
            assert revision_response.status_code == 200
            assert revision_response.json()["archive_event"]["archive_uri"].endswith("_r2.json")
            assert (await client.get(f"/api/v1/cases/{proposal['case_id']}")).json()["archive_revision"] == 2

    asyncio.run(exercise())


def test_webhook_time_window_rejects_expired_and_future_results() -> None:
    cases = InMemoryQualityCaseStore()
    service = QmsWebhookService(
        cases,
        b"secret",
        clock=lambda: datetime(2026, 8, 23, 12, tzinfo=UTC),
        max_age=timedelta(minutes=5),
    )
    result = _result("case-missing", "task-missing")
    expired = result.model_copy(update={"occurred_at": datetime(2026, 8, 23, 11, 0, tzinfo=UTC)})
    expired_signature = sign_qms_result(expired, b"secret")
    with pytest.raises(ValueError, match="outside the allowed time window"):
        service.process(expired, expired_signature)
    future = result.model_copy(update={"occurred_at": datetime(2026, 8, 23, 12, 10, tzinfo=UTC)})
    future_signature = sign_qms_result(future, b"secret")
    with pytest.raises(ValueError, match="in the future"):
        service.process(future, future_signature)


def test_not_verified_result_is_archived_but_not_promoted() -> None:
    async def exercise() -> None:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/demo/fixture-offset")
            proposal = (await client.get("/api/v1/proposals/pending")).json()[0]
            decision = {
                "decision_id": "decision-phase9-not-verified-001",
                "proposal_id": proposal["proposal_id"],
                "case_id": proposal["case_id"],
                "decision": "APPROVE",
                "decided_by": "engineer-phase9",
                "decided_at": datetime.now(UTC).isoformat(),
            }
            await client.post(
                f"/api/v1/proposals/{proposal['proposal_id']}/decisions", json=decision
            )
            task = (await client.get("/api/v1/qms/tasks")).json()["items"][0]
            result = _result(proposal["case_id"], task["task_id"], status="NOT_VERIFIED")
            response = await client.post(
                "/api/v1/integrations/qms/task-results",
                json=result.model_dump(mode="json"),
                headers={"X-QMS-Signature": sign_qms_result(result, b"phase9-demo-secret")},
            )
            assert response.status_code == 200
            assert response.json()["archive_event"]["knowledge_index_status"] == "NOT_ELIGIBLE"
            assert (await client.get("/api/v1/case-library")).json() == []

    asyncio.run(exercise())
