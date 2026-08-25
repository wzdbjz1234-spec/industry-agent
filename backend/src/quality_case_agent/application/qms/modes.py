"""QMS execution modes and a side-effect-free Shadow adapter."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from quality_case_agent.application.ports.qms import QmsClient
from quality_case_agent.contracts.investigation import ProposalContract
from quality_case_agent.contracts.qms import QmsTaskContract

QmsMode = Literal["SHADOW", "SANDBOX", "PRODUCTION"]


class QmsModePolicy:
    version = "qms-mode-policy-v1"

    @staticmethod
    def validate(mode: str) -> QmsMode:
        normalized = mode.strip().upper()
        if normalized not in {"SHADOW", "SANDBOX", "PRODUCTION"}:
            raise ValueError("QMS mode must be SHADOW, SANDBOX, or PRODUCTION")
        return normalized  # type: ignore[return-value]

    @staticmethod
    def allows_external_write(mode: QmsMode) -> bool:
        return mode in {"SANDBOX", "PRODUCTION"}


class ShadowQmsAdapter(QmsClient):
    """Produce a deterministic planned task without calling any external write endpoint."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._tasks: dict[str, QmsTaskContract] = {}

    def create_task(self, proposal: ProposalContract) -> QmsTaskContract:
        if proposal.status != "APPROVED":
            raise ValueError("only an approved Proposal can create a shadow QMS task")
        existing = self._tasks.get(proposal.proposal_id)
        if existing is not None:
            return existing
        task_id = f"SHADOW-{uuid5(NAMESPACE_URL, proposal.proposal_id).hex[:16]}"
        task = QmsTaskContract(
            task_id=task_id,
            case_id=proposal.case_id,
            proposal_id=proposal.proposal_id,
            external_system="SHADOW_QMS",
            assignee_role=proposal.requested_role,
            created_by="shadow-qms-planner",
            created_at=self._clock(),
            task_uri=f"shadow://qms/tasks/{task_id}",
        )
        self._tasks[proposal.proposal_id] = task
        return task

    def get_task_by_proposal(self, proposal_id: str) -> QmsTaskContract | None:
        return self._tasks.get(proposal_id)

    def get_task(self, task_id: str) -> QmsTaskContract | None:
        return next((task for task in self._tasks.values() if task.task_id == task_id), None)

    def list_tasks(self) -> tuple[QmsTaskContract, ...]:
        return tuple(self._tasks.values())
