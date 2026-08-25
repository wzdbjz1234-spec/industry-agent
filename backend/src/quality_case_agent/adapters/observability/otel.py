"""OpenTelemetry implementation plus an assertion-friendly in-memory tracer."""

from __future__ import annotations

import re
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from quality_case_agent.application.ports.telemetry import TelemetryOperation

_SECRET = re.compile(r"(?i)(token|password|secret|api[_-]?key)=([^\s,;]+)")
_SENSITIVE_KEYS = {"prompt", "completion", "document_text", "image_bytes", "api_key", "token"}
_current_trace_id: ContextVar[str | None] = ContextVar("quality_trace_id", default=None)


def sanitize_attributes(attributes: Mapping[str, object] | None) -> dict[str, str | int | float | bool]:
    result: dict[str, str | int | float | bool] = {}
    for key, value in (attributes or {}).items():
        if key.lower() in _SENSITIVE_KEYS:
            continue
        if isinstance(value, (str, int, float, bool)):
            result[key] = _SECRET.sub(r"\1=[REDACTED]", value) if isinstance(value, str) else value
    return result


@dataclass(slots=True)
class SpanRecord:
    name: str
    trace_id: str
    span_id: str
    attributes: dict[str, str | int | float | bool]
    status: str = "UNSET"
    duration_ms: float = 0.0
    events: list[tuple[str, dict[str, str | int | float | bool]]] = field(default_factory=list)


class _MemoryOperation(TelemetryOperation):
    def __init__(self, record: SpanRecord) -> None:
        self.record = record

    def set_attribute(self, key: str, value: str | float | bool) -> None:
        self.record.attributes.update(sanitize_attributes({key: value}))

    def add_event(self, name: str, attributes: Mapping[str, str | int | float | bool] | None = None) -> None:
        self.record.events.append((name, sanitize_attributes(attributes)))

    def succeed(self, **attributes: str | float | bool) -> None:
        self.record.status = "OK"
        self.record.attributes.update(sanitize_attributes(attributes))

    def fail(self, error: BaseException, **attributes: str | float | bool) -> None:
        self.record.status = "ERROR"
        self.record.attributes.update(sanitize_attributes(attributes))
        self.record.attributes["error.type"] = type(error).__name__


class InMemoryTelemetry:
    def __init__(self) -> None:
        self.spans: list[SpanRecord] = []

    @property
    def current_trace_id(self) -> str | None:
        return _current_trace_id.get()

    @contextmanager
    def operation(self, name: str, *, attributes: Mapping[str, object] | None = None) -> Iterator[_MemoryOperation]:
        trace_id = _current_trace_id.get() or uuid4().hex
        token = _current_trace_id.set(trace_id)
        record = SpanRecord(name, trace_id, uuid4().hex[:16], sanitize_attributes(attributes))
        started = time.perf_counter()
        self.spans.append(record)
        operation = _MemoryOperation(record)
        try:
            yield operation
            if record.status == "UNSET":
                operation.succeed()
        except BaseException as exc:
            operation.fail(exc)
            raise
        finally:
            record.duration_ms = (time.perf_counter() - started) * 1000
            _current_trace_id.reset(token)


class _OtelOperation(TelemetryOperation):
    def __init__(self, span: Any) -> None:
        self.span = span

    def set_attribute(self, key: str, value: str | float | bool) -> None:
        self.span.set_attribute(key, value)

    def add_event(self, name: str, attributes: Mapping[str, str | int | float | bool] | None = None) -> None:
        self.span.add_event(name, attributes=dict(attributes or {}))

    def succeed(self, **attributes: str | float | bool) -> None:
        from opentelemetry.trace import Status, StatusCode

        self.span.set_status(Status(StatusCode.OK))
        self.span.set_attributes(sanitize_attributes(attributes))

    def fail(self, error: BaseException, **attributes: str | float | bool) -> None:
        from opentelemetry.trace import Status, StatusCode

        self.span.record_exception(error)
        self.span.set_status(Status(StatusCode.ERROR, str(error)[:512]))
        self.span.set_attributes(sanitize_attributes(attributes))


class OtelTelemetry:
    def __init__(self, tracer: Any | None = None, *, service_name: str = "quality-case-agent") -> None:
        if tracer is None:
            from opentelemetry import trace

            tracer = trace.get_tracer(service_name)
        self.tracer = tracer

    @contextmanager
    def operation(self, name: str, *, attributes: Mapping[str, object] | None = None) -> Iterator[_OtelOperation]:
        with self.tracer.start_as_current_span(name) as span:
            span.set_attributes(sanitize_attributes(attributes))
            operation = _OtelOperation(span)
            try:
                yield operation
                operation.succeed()
            except BaseException as exc:
                operation.fail(exc)
                raise
