"""HTTP read-only equipment adapter with an injected client for testing."""

from datetime import datetime
from typing import Any

import httpx

from quality_case_agent.application.ports.equipment import EquipmentState


class HttpEquipmentAdapter:
    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client()

    def get_state(self, station_id: str) -> EquipmentState:
        response = self._client.get(f"{self._base_url}/equipment/{station_id}")
        response.raise_for_status()
        payload: Any = response.json()
        if not isinstance(payload, dict):
            raise TypeError("equipment response must be an object")
        observed_at = datetime.fromisoformat(str(payload["observed_at"]))
        return EquipmentState(
            station_id=str(payload.get("station_id", station_id)),
            observed_at=observed_at,
            state=str(payload["state"]),
            attributes=payload.get("attributes", {}) if isinstance(payload.get("attributes", {}), dict) else {},
        )
