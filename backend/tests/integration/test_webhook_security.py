"""Phase 21 timestamped webhook signatures reject stale or replayed deliveries."""

from datetime import UTC, datetime, timedelta

import pytest
from quality_case_agent.adapters.in_memory.stores import InMemoryQualityCaseStore
from quality_case_agent.application.qms.service import QmsWebhookService
from quality_case_agent.contracts.qms import (
    ActualRootCauseContract,
    AgentAssessmentContract,
    QmsTaskResultContract,
    VerificationContract,
)


def _result() -> QmsTaskResultContract:
    now = datetime.now(UTC)
    return QmsTaskResultContract(
        event_id="phase21-webhook-1",
        occurred_at=now,
        confirmation_id="confirmation-1",
        case_id="case-1",
        task_id="task-1",
        confirmed_by="qms",
        actual_root_cause=ActualRootCauseContract(code="fixture", description="fixture"),
        actual_actions=["replace"],
        verification=VerificationContract(
            status="VERIFIED_EFFECTIVE",
            start=now - timedelta(minutes=2),
            end=now,
            sample_count=10,
            ng_rate_before=0.1,
            ng_rate_after=0.01,
            acceptance_criteria="ng rate falls",
        ),
        agent_assessment=AgentAssessmentContract(
            top_hypothesis_matched=True,
            useful=True,
            human_rating=5,
        ),
    )


def test_stale_timestamp_is_rejected_before_case_lookup() -> None:
    result = _result()
    service = QmsWebhookService(InMemoryQualityCaseStore(), b"phase21", clock=lambda: datetime.now(UTC))
    timestamp = str((datetime.now(UTC) - timedelta(days=8)).timestamp())
    signature = service.sign_with_timestamp(result, timestamp=timestamp, nonce="nonce-1")
    with pytest.raises(ValueError, match="outside the allowed time window"):
        service.process(result, signature, timestamp=timestamp, nonce="nonce-1")
