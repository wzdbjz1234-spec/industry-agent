"""Phase 10 archive promotion -> second Case -> C-level historical evidence tests."""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
from quality_case_agent.application.qms.service import sign_qms_result
from quality_case_agent.contracts.qms import (
    ActualRootCauseContract,
    AgentAssessmentContract,
    QmsTaskResultContract,
    VerificationContract,
)
from quality_case_agent.entrypoints.api.app import create_app


def _result(case_id: str, task_id: str, suffix: str) -> QmsTaskResultContract:
    now = datetime.now(UTC)
    return QmsTaskResultContract(
        event_id=f"qms-result-phase10-{suffix}",
        occurred_at=now,
        confirmation_id=f"confirmation-phase10-{suffix}",
        case_id=case_id,
        task_id=task_id,
        confirmed_by="engineer-phase10",
        actual_root_cause=ActualRootCauseContract(
            code="FIXTURE_LOCATING_PIN_LOOSE", description="定位销松动导致右上偏移"
        ),
        actual_actions=["更换定位销"],
        verification=VerificationContract(
            status="VERIFIED_EFFECTIVE",
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
            comment="历史经验只用于缩小排查范围。",
        ),
    )


def test_second_fixture_case_reuses_archive_as_c_level_evidence() -> None:
    async def exercise() -> None:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first_seed = await client.post("/api/v1/demo/fixture-offset")
            first_case_id = first_seed.json()["case_ids"][0]
            first_proposal = (await client.get("/api/v1/proposals/pending")).json()[0]
            decision = {
                "decision_id": "decision-phase10-first",
                "proposal_id": first_proposal["proposal_id"],
                "case_id": first_case_id,
                "decision": "APPROVE",
                "decided_by": "engineer-phase10",
                "decided_at": datetime.now(UTC).isoformat(),
            }
            await client.post(
                f"/api/v1/proposals/{first_proposal['proposal_id']}/decisions", json=decision
            )
            first_task = (await client.get("/api/v1/qms/tasks")).json()["items"][0]
            first_result = _result(first_case_id, first_task["task_id"], "first")
            response = await client.post(
                "/api/v1/integrations/qms/task-results",
                json=first_result.model_dump(mode="json"),
                headers={"X-QMS-Signature": sign_qms_result(first_result, b"phase9-demo-secret")},
            )
            assert response.status_code == 200
            library = (await client.get("/api/v1/case-library")).json()
            assert library[0]["metadata"]["trigger_family"] == "FIXTURE_OFFSET"
            assert library[0]["metadata"]["archive_uri"]

            second_seed = await client.post("/api/v1/demo/fixture-offset/repeat")
            next(
                case_id for case_id in second_seed.json()["case_ids"] if case_id != first_case_id
            )
            second_proposals = (await client.get("/api/v1/proposals/pending")).json()
            assert len(second_proposals) == 1
            second_proposal = second_proposals[0]
            output = (
                await client.get(f"/api/v1/analysis/runs/{second_proposal['analysis_run_id']}")
            ).json()
            historical = [
                evidence
                for evidence in output["analysis"]["evidence"]
                if evidence["evidence_type"] == "VERIFIED_CASE"
            ]
            assert historical
            assert all(item["evidence_class"] == "C" for item in historical)
            assert all(item["applicability"] == "CONTEXTUAL" for item in historical)
            assert all("不能证明本次根因" in item["claim"] for item in historical)
            assert historical[0]["reference"] == library[0]["metadata"]["archive_uri"]
            assert any("C级经验" in item for item in output["analysis"]["limitations"])

            archive = (await client.get(f"/api/v1/case-library/{first_case_id}")).json()
            assert archive["case"]["case_id"] == first_case_id
            assert archive["human_confirmation"]["verification"]["status"] == "VERIFIED_EFFECTIVE"
            wrong_product = await client.get(
                "/api/v1/knowledge/search",
                params={
                    "query": "定位销 右上 偏移",
                    "source_type": "VERIFIED_CASE",
                    "station_id": "camera-01",
                    "product_id": "part-B",
                    "trigger_family": "FIXTURE_OFFSET",
                },
            )
            assert wrong_product.status_code == 200
            assert wrong_product.json() == []

    asyncio.run(exercise())
