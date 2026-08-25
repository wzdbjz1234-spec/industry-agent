"""Read-only equipment/environment port used by investigation Runbooks."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EquipmentState:
    station_id: str
    observed_at: datetime
    state: str
    attributes: Mapping[str, object] = field(default_factory=dict)


class EquipmentPort(Protocol):
    def get_state(self, station_id: str) -> EquipmentState:
        """Read the latest state; implementations must not mutate equipment."""
