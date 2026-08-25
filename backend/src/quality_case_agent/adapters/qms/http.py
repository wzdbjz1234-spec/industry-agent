"""HTTP QMS adapter; the Investigation Agent never imports this module."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from quality_case_agent.application.ports.qms import (
    QmsPermanentError,
    QmsTransientError,
)
from quality_case_agent.application.qms.modes import QmsMode, QmsModePolicy
from quality_case_agent.contracts.investigation import ProposalContract
from quality_case_agent.contracts.qms import QmsCreateTaskRequestContract, QmsTaskContract


class HttpQmsClient:
    """Translate the QMS Port to the standalone Mock/enterprise REST API."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 5.0,
        client: httpx.Client | None = None,
        mode: QmsMode = "SANDBOX",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)
        self._mode = QmsModePolicy.validate(mode)
        if not QmsModePolicy.allows_external_write(self._mode):
            raise ValueError("HttpQmsClient cannot be configured for SHADOW mode")

    def create_task(self, proposal: ProposalContract) -> QmsTaskContract:
        request = QmsCreateTaskRequestContract(
            proposal_id=proposal.proposal_id,
            case_id=proposal.case_id,
            title=proposal.title,
            reason=proposal.reason,
            steps=proposal.steps,
            assignee_role=proposal.requested_role,
            priority=proposal.priority,
            risk_level=proposal.risk_level,
        )
        response = self._request(
            "POST",
            "/api/v1/tasks",
            json=request.model_dump(mode="json"),
            headers={"Idempotency-Key": proposal.proposal_id},
        )
        return QmsTaskContract.model_validate(response)

    def get_task_by_proposal(self, proposal_id: str) -> QmsTaskContract | None:
        try:
            response = self._request(
                "GET", f"/api/v1/tasks/by-proposal/{quote(proposal_id, safe='')}"
            )
        except QmsPermanentError as exc:
            if str(exc).startswith("404:"):
                return None
            raise
        return QmsTaskContract.model_validate(response)

    def get_task(self, task_id: str) -> QmsTaskContract | None:
        try:
            response = self._request("GET", f"/api/v1/tasks/{quote(task_id, safe='')}")
        except QmsPermanentError as exc:
            if str(exc).startswith("404:"):
                return None
            raise
        return QmsTaskContract.model_validate(response)

    def list_tasks(self) -> tuple[QmsTaskContract, ...]:
        response = self._request("GET", "/api/v1/tasks")
        items = response.get("items", [])
        if not isinstance(items, list):
            raise QmsPermanentError("QMS returned an invalid task list")
        return tuple(QmsTaskContract.model_validate(item) for item in items)

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, object]:
        try:
            response = self._client.request(method, f"{self._base_url}{path}", **kwargs)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise QmsTransientError(f"QMS request failed: {exc}") from exc
        if response.status_code == 429 or response.status_code >= 500:
            raise QmsTransientError(f"{response.status_code}: QMS temporary failure")
        if response.status_code >= 400:
            raise QmsPermanentError(f"{response.status_code}: {response.text[:256]}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise QmsPermanentError("QMS returned non-JSON data") from exc
        if not isinstance(payload, dict):
            raise QmsPermanentError("QMS returned a non-object response")
        return payload
