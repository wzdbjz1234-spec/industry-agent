"""Provider-neutral tracing seam for API, workers and Agent operations."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from typing import Protocol


class TelemetryOperation(Protocol):
    def set_attribute(self, key: str, value: str | float | bool) -> None: ...

    def add_event(self, name: str, attributes: Mapping[str, str | int | float | bool] | None = None) -> None: ...

    def succeed(self, **attributes: str | float | bool) -> None: ...

    def fail(self, error: BaseException, **attributes: str | float | bool) -> None: ...


class Telemetry(Protocol):
    def operation(
        self,
        name: str,
        *,
        attributes: Mapping[str, str | int | float | bool] | None = None,
    ) -> AbstractContextManager[TelemetryOperation]:
        """Create a span with sanitized low-cardinality attributes."""

