"""Event recording and rolling NG-rate fluctuation detection."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from quality_case_agent.contracts.vision import (
    NgRateFluctuationEventContract,
    VisionFaultEventContract,
)


class InMemoryVisionEventStore:
    """Replaceable event sink for the offline runtime."""

    def __init__(self) -> None:
        self._events: dict[str, VisionFaultEventContract | NgRateFluctuationEventContract] = {}

    def append(self, event: VisionFaultEventContract | NgRateFluctuationEventContract) -> None:
        self._events.setdefault(event.event_id, event)

    def list_events(self, event_type: str | None = None) -> Sequence[object]:
        events = sorted(self._events.values(), key=lambda item: item.occurred_at)
        if event_type is None:
            return tuple(events)
        return tuple(item for item in events if item.event_type == event_type)

    @property
    def count(self) -> int:
        return len(self._events)


@dataclass(frozen=True, slots=True)
class _Observation:
    inspected_at: datetime
    is_ng: bool


class NgRateFluctuationTracker:
    """Detect rising/falling changes between two halves of a rolling window."""

    def __init__(self, *, window_size: int = 20, minimum_samples: int = 6, delta_threshold: float = 0.25) -> None:
        if minimum_samples < 2 or window_size < minimum_samples:
            raise ValueError("window_size must be >= minimum_samples >= 2")
        self.window_size = window_size
        self.minimum_samples = minimum_samples
        self.delta_threshold = delta_threshold
        self._observations: dict[str, deque[_Observation]] = defaultdict(
            lambda: deque(maxlen=self.window_size)
        )

    def observe(
        self,
        *,
        scope_key: str,
        scope: dict[str, str],
        inspected_at: datetime,
        is_ng: bool,
        trace_id: str,
    ) -> NgRateFluctuationEventContract | None:
        history = self._observations[scope_key]
        history.append(_Observation(inspected_at=inspected_at, is_ng=is_ng))
        if len(history) < self.minimum_samples:
            return None
        split = len(history) // 2
        baseline = list(history)[:split]
        recent = list(history)[split:]
        baseline_rate = sum(item.is_ng for item in baseline) / len(baseline)
        recent_rate = sum(item.is_ng for item in recent) / len(recent)
        delta = recent_rate - baseline_rate
        if abs(delta) < self.delta_threshold:
            return None
        direction: Literal["RISING", "FALLING"] = "RISING" if delta > 0 else "FALLING"
        event_id = f"ng-fluctuation:{scope_key}:{trace_id}:{direction}"
        return NgRateFluctuationEventContract(
            event_id=event_id,
            occurred_at=inspected_at,
            trace_id=trace_id,
            scope=scope,
            window_start=history[0].inspected_at,
            window_end=history[-1].inspected_at,
            sample_count=len(history),
            baseline_ng_rate=round(baseline_rate, 6),
            recent_ng_rate=round(recent_rate, 6),
            delta=round(delta, 6),
            direction=direction,
            details={"window_size": self.window_size, "minimum_samples": self.minimum_samples},
        )
