"""QMS integration ports and failure categories."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, Protocol

from quality_case_agent.contracts.approval import ApprovalEventContract
from quality_case_agent.contracts.investigation import ProposalContract
from quality_case_agent.contracts.qms import QmsTaskContract, QmsTaskCreatedEventContract


class QmsTransientError(RuntimeError):
    """The QMS may succeed when the message is retried."""


class QmsPermanentError(RuntimeError):
    """The request is invalid and should be sent to the DLQ."""


@dataclass(slots=True)
class QmsDeliveryRecord:
    """Durable-looking delivery state used by the local worker implementation."""

    event: ApprovalEventContract
    consumer_group: str
    attempts: int
    state: Literal["PENDING", "PROCESSED", "DLQ"]
    last_error: str | None = None
    result: QmsTaskCreatedEventContract | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_error_type: str | None = None
    last_error_at: datetime | None = None


class QmsDeliveryStore(Protocol):
    def get(self, event_id: str, consumer_group: str) -> QmsDeliveryRecord | None:
        """Return one delivery record by its consumer-group idempotency key."""

    def save(self, record: QmsDeliveryRecord) -> None:
        """Insert or update a delivery record."""

    def list_pending(self, consumer_group: str) -> Sequence[QmsDeliveryRecord]:
        """Return deliveries that may be retried."""

    def list_dlq(self, consumer_group: str) -> Sequence[QmsDeliveryRecord]:
        """Return permanently failed deliveries."""

    def list_processed(self, consumer_group: str) -> Sequence[QmsDeliveryRecord]:
        """Return successfully processed deliveries."""


class QmsClient(Protocol):
    def create_task(self, proposal: ProposalContract) -> QmsTaskContract:
        """Create or return the task associated with a Proposal."""

    def get_task_by_proposal(self, proposal_id: str) -> QmsTaskContract | None:
        """Find an external task by the idempotency key."""

    def get_task(self, task_id: str) -> QmsTaskContract | None:
        """Find an external task by its task identifier."""

    def list_tasks(self) -> Sequence[QmsTaskContract]:
        """List tasks for an operations view."""
