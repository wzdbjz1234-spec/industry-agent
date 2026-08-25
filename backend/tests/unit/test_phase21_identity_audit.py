"""Phase 21 identity, policy and append-only audit tests."""

from datetime import UTC, datetime

import pytest
from quality_case_agent.adapters.in_memory.audit import InMemoryAuditLog
from quality_case_agent.application.audit.service import AuditService
from quality_case_agent.application.identity.policy import (
    AuthorizationDenied,
    HeaderIdentityProvider,
    IdentityPolicy,
)


def test_identity_policy_blocks_viewer_from_approval_and_audit_redacts_secret() -> None:
    provider = HeaderIdentityProvider()
    viewer = provider.authenticate({"X-Actor-Id": "viewer-1", "X-Actor-Role": "VIEWER"})
    with pytest.raises(AuthorizationDenied):
        IdentityPolicy().authorize(viewer, "proposal.decide")

    log = InMemoryAuditLog()
    service = AuditService(log)
    service.record(
        viewer,
        event_type="test.audit.v1",
        action="READ",
        resource_type="case",
        resource_id="case-1",
        correlation_id="corr-1",
        metadata={"api_key": "do-not-store", "note": "safe"},
        occurred_at=datetime(2026, 8, 25, tzinfo=UTC),
    )
    event = log.list_events()[0]
    assert event.metadata["api_key"] == "[REDACTED]"
    assert log.verify_chain()
    assert "do-not-store" not in log.export_jsonl()


def test_identity_header_provider_requires_identity_when_configured() -> None:
    provider = HeaderIdentityProvider(required=True)
    with pytest.raises(ValueError):
        provider.authenticate({})
