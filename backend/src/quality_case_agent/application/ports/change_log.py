"""Read-only change-log port for correlating process changes with quality Cases."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ChangeRecord:
    change_id: str
    station_id: str
    occurred_at: datetime
    change_type: str
    summary: str
    metadata: Mapping[str, object] = field(default_factory=dict)


class ChangeLogPort(Protocol):
    def list_recent(self, station_id: str, since: datetime) -> Sequence[ChangeRecord]:
        """Return immutable, read-only change records after ``since``."""
