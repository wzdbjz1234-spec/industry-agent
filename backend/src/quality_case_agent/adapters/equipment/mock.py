"""Deterministic equipment adapter for tests and local development."""

from quality_case_agent.application.ports.equipment import EquipmentState


class MockEquipmentAdapter:
    def __init__(self, states: dict[str, EquipmentState] | None = None) -> None:
        self._states = dict(states or {})

    def get_state(self, station_id: str) -> EquipmentState:
        if station_id not in self._states:
            raise KeyError(f"equipment state not found: {station_id}")
        return self._states[station_id]
