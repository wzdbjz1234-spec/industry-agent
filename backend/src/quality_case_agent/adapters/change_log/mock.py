"""Deterministic change-log adapter for tests and local development."""

from datetime import datetime

from quality_case_agent.application.ports.change_log import ChangeRecord


class MockChangeLogAdapter:
    def __init__(self, records: list[ChangeRecord] | None = None) -> None:
        self._records = list(records or [])

    def list_recent(self, station_id: str, since: datetime) -> list[ChangeRecord]:
        return [
            record
            for record in self._records
            if record.station_id == station_id and record.occurred_at >= since
        ]
