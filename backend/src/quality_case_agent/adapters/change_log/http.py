"""HTTP read-only change-log adapter with an injected client for testing."""

from datetime import datetime
from typing import Any

import httpx

from quality_case_agent.application.ports.change_log import ChangeRecord


class HttpChangeLogAdapter:
    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client()

    def list_recent(self, station_id: str, since: datetime) -> list[ChangeRecord]:
        response = self._client.get(
            f"{self._base_url}/changes",
            params={"station_id": station_id, "since": since.isoformat()},
        )
        response.raise_for_status()
        payload: Any = response.json()
        if not isinstance(payload, list):
            raise TypeError("change-log response must be an array")
        records: list[ChangeRecord] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            records.append(
                ChangeRecord(
                    change_id=str(item["change_id"]),
                    station_id=str(item.get("station_id", station_id)),
                    occurred_at=datetime.fromisoformat(str(item["occurred_at"])),
                    change_type=str(item["change_type"]),
                    summary=str(item["summary"]),
                    metadata=item.get("metadata", {}) if isinstance(item.get("metadata", {}), dict) else {},
                )
            )
        return records
