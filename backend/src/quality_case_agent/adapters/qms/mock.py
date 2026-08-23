"""Deterministic Mock QMS adapter with Proposal idempotency."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from quality_case_agent.application.ports.qms import QmsTransientError
from quality_case_agent.contracts.investigation import ProposalContract
from quality_case_agent.contracts.qms import QmsCreateTaskRequestContract, QmsTaskContract


class MockQmsAdapter:
    """In-memory implementation shared by the worker and standalone Mock QMS API."""

    def __init__(
        self,
        clock: Callable[[], datetime] | None = None,
        *,
        base_uri: str = "http://localhost:8001",
    ) -> None:
        self._tasks: dict[str, QmsTaskContract] = {}
        self._clock = clock or (lambda: datetime.now(UTC))
        self._base_uri = base_uri.rstrip("/")
        self._available = True
        self._failures_remaining = 0

    def create_task(self, proposal: ProposalContract) -> QmsTaskContract:
        if proposal.status != "APPROVED":
            raise ValueError("only an approved Proposal can create a QMS task")
        self._ensure_available()
        existing = self._tasks.get(proposal.proposal_id)
        if existing is not None:
            return existing
        return self._create(
            QmsCreateTaskRequestContract(
                proposal_id=proposal.proposal_id,
                case_id=proposal.case_id,
                title=proposal.title,
                reason=proposal.reason,
                steps=proposal.steps,
                assignee_role=proposal.requested_role,
                priority=proposal.priority,
                risk_level=proposal.risk_level,
            )
        )

    def create_task_request(self, request: QmsCreateTaskRequestContract) -> QmsTaskContract:
        """Create from the HTTP boundary without exposing Proposal internals to Mock QMS."""

        self._ensure_available()
        return self._create(request)

    def _create(self, request: QmsCreateTaskRequestContract) -> QmsTaskContract:
        existing = self._tasks.get(request.proposal_id)
        if existing is not None:
            return existing
        task_number = len(self._tasks) + 1
        task = QmsTaskContract(
            task_id=f"QMS-TASK-{task_number:04d}",
            case_id=request.case_id,
            proposal_id=request.proposal_id,
            created_at=self._clock(),
            assignee_role=request.assignee_role,
            created_by="quality-integration-service",
            task_uri=f"{self._base_uri}/tasks/QMS-TASK-{task_number:04d}",
        )
        self._tasks[request.proposal_id] = task
        return task

    def get_task_by_proposal(self, proposal_id: str) -> QmsTaskContract | None:
        return self._tasks.get(proposal_id)

    def get_task(self, task_id: str) -> QmsTaskContract | None:
        return next((task for task in self._tasks.values() if task.task_id == task_id), None)

    def list_tasks(self) -> tuple[QmsTaskContract, ...]:
        return tuple(sorted(self._tasks.values(), key=lambda task: task.task_id))

    def set_status(self, task_id: str, status: Literal["OPEN", "IN_PROGRESS", "CLOSED"]) -> QmsTaskContract:
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        updated = task.model_copy(update={"status": status})
        self._tasks[task.proposal_id] = updated
        return updated

    def set_available(self, available: bool) -> None:
        self._available = available

    def fail_next(self, count: int = 1) -> None:
        if count < 1:
            raise ValueError("failure count must be positive")
        self._failures_remaining = count

    def _ensure_available(self) -> None:
        if not self._available or self._failures_remaining:
            if self._failures_remaining:
                self._failures_remaining -= 1
            raise QmsTransientError("Mock QMS is temporarily unavailable")

    @property
    def task_count(self) -> int:
        return len(self._tasks)
