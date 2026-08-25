"""Safe, provider-neutral projections for Case timelines and worker operations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

_SECRET = re.compile(r"(?i)(token|password|secret|api[_-]?key)=([^\s,;]+)")
_URL = re.compile(r"https?://[^\s]+")


def redact_error(message: str, limit: int = 512) -> str:
    """Keep an error category useful while removing common credentials and URLs."""

    value = _SECRET.sub(r"\1=[REDACTED]", message)
    value = _URL.sub("[URL_REDACTED]", value)
    return " ".join(value.split())[:limit] or "operation failed"


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    event_id: str
    event_type: str
    occurred_at: datetime
    case_id: str | None
    trace_id: str | None
    source: str
    state: str | None
    summary: str

    def as_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "case_id": self.case_id,
            "trace_id": self.trace_id,
            "source": self.source,
            "state": self.state,
            "summary": self.summary,
        }


class CaseEventTimelineProjection:
    """Idempotent read projection assembled from domain/application events."""

    def __init__(self) -> None:
        self._entries: dict[str, TimelineEntry] = {}

    def record(
        self,
        event: object,
        *,
        source: str,
        state: str | None = None,
        summary: str | None = None,
        event_id: str | None = None,
    ) -> TimelineEntry:
        resolved_event_id = event_id or str(getattr(event, "event_id", ""))
        if not resolved_event_id:
            raise ValueError("timeline event must have an event_id")
        existing = self._entries.get(resolved_event_id)
        if existing is not None:
            return existing
        event_type = str(getattr(event, "event_type", type(event).__name__))
        occurred_at = getattr(event, "occurred_at", datetime.now(UTC))
        if not isinstance(occurred_at, datetime):
            occurred_at = datetime.now(UTC)
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=UTC)
        case_id = self._case_id(event)
        trace_id = self._trace_id(event, case_id)
        entry = TimelineEntry(
            event_id=resolved_event_id,
            event_type=event_type,
            occurred_at=occurred_at.astimezone(UTC),
            case_id=case_id,
            trace_id=trace_id,
            source=source,
            state=state,
            summary=summary or self._default_summary(event_type, state),
        )
        self._entries[resolved_event_id] = entry
        return entry

    def record_delivery(self, delivery: object, *, source: str = "qms-delivery") -> TimelineEntry:
        event = getattr(delivery, "event", None)
        if event is None:
            raise ValueError("delivery record must contain an event")
        event_id = (
            f"delivery:{getattr(delivery, 'consumer_group', 'unknown')}:{event.event_id}:"
            f"{getattr(delivery, 'state', 'UNKNOWN')}:{getattr(delivery, 'attempts', 0)}"
        )
        error = getattr(delivery, "last_error", None)
        summary = f"投递状态 {getattr(delivery, 'state', 'UNKNOWN')}，尝试次数 {getattr(delivery, 'attempts', 0)}"
        if error:
            summary += f"，错误：{redact_error(str(error), 180)}"
        return self.record(
            event,
            source=source,
            state=str(getattr(delivery, "state", "UNKNOWN")),
            summary=summary,
            event_id=event_id,
        )

    def list(self, *, case_id: str | None = None, trace_id: str | None = None) -> tuple[TimelineEntry, ...]:
        return tuple(
            sorted(
                (
                    entry
                    for entry in self._entries.values()
                    if (case_id is None or entry.case_id == case_id)
                    and (trace_id is None or entry.trace_id == trace_id)
                ),
                key=lambda entry: (entry.occurred_at, entry.event_id),
            )
        )

    @staticmethod
    def _case_id(event: object) -> str | None:
        direct = getattr(event, "case_id", None)
        if isinstance(direct, str):
            return direct
        proposal = getattr(event, "proposal", None)
        proposal_case = getattr(proposal, "case_id", None)
        if isinstance(proposal_case, str):
            return proposal_case
        task = getattr(event, "task", None)
        task_case = getattr(task, "case_id", None)
        return task_case if isinstance(task_case, str) else None

    @staticmethod
    def _trace_id(event: object, case_id: str | None) -> str | None:
        for attribute in ("trace_id", "analysis_run_id", "trigger_event_id"):
            value = getattr(event, attribute, None)
            if isinstance(value, str) and value:
                return value
        return f"case:{case_id}" if case_id else None

    @staticmethod
    def _default_summary(event_type: str, state: str | None) -> str:
        return f"{event_type}{f' ({state})' if state else ''}"


@dataclass(slots=True)
class _WorkerCounter:
    processed: int = 0
    failed: int = 0
    pending: int = 0
    dlq: int = 0
    total_duration_ms: int = 0
    error_count: int = 0
    last_error_type: str | None = None
    last_error_category: str | None = None
    last_error: str | None = None
    last_event_id: str | None = None
    last_processed_at: datetime | None = None


class WorkerMetricsRegistry:
    """Low-cardinality worker counters suitable for an operations endpoint."""

    def __init__(self, exporter: object | None = None) -> None:
        self._workers: dict[str, _WorkerCounter] = {}
        self._exporter = exporter

    def observe(
        self,
        worker: str,
        *,
        status: str,
        duration_ms: int,
        event_id: str | None = None,
        error_type: str | None = None,
        error: str | None = None,
        error_category: str | None = None,
    ) -> None:
        counter = self._workers.setdefault(worker, _WorkerCounter())
        counter.total_duration_ms += max(0, duration_ms)
        counter.last_event_id = event_id
        counter.last_processed_at = datetime.now(UTC)
        if status == "PROCESSED":
            counter.processed += 1
        elif status == "PENDING":
            counter.pending += 1
            counter.failed += 1
        elif status == "DLQ":
            counter.dlq += 1
            counter.failed += 1
        else:
            counter.failed += 1
        if error:
            counter.error_count += 1
            counter.last_error_type = error_type or "RuntimeError"
            counter.last_error_category = error_category or "SYSTEM_FAILURE"
            counter.last_error = redact_error(error)
        record_worker = getattr(self._exporter, "record_worker", None)
        if callable(record_worker):
            record_worker(
                worker,
                status=status,
                duration_ms=duration_ms,
                error_category=error_category or ("NONE" if not error else "SYSTEM_FAILURE"),
            )

    def snapshot(self) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for worker, counter in sorted(self._workers.items()):
            total = counter.processed + counter.failed
            result.append(
                {
                    "worker": worker,
                    "processed": counter.processed,
                    "failed": counter.failed,
                    "pending": counter.pending,
                    "dlq": counter.dlq,
                    "error_count": counter.error_count,
                    "avg_latency_ms": round(counter.total_duration_ms / total, 2)
                    if total
                    else 0.0,
                    "last_error_type": counter.last_error_type,
                    "last_error_category": counter.last_error_category,
                    "last_error": counter.last_error,
                    "last_event_id": counter.last_event_id,
                    "last_processed_at": (
                        counter.last_processed_at.isoformat()
                        if counter.last_processed_at
                        else None
                    ),
                }
            )
        return result


class AnalysisMetricsRegistry:
    """Structured analysis cost/tool metrics, without model chain-of-thought."""

    def __init__(self, exporter: object | None = None, *, provider: str = "unknown", model: str = "unknown") -> None:
        self._records: dict[str, dict[str, object]] = {}
        self._exporter = exporter
        self._provider = provider
        self._model = model

    def record(
        self,
        *,
        run_id: str,
        case_id: str,
        status: str,
        duration_ms: int,
        tool_call_count: int,
        retrieval_call_count: int,
        estimated_tokens: int,
        estimated_cost_cny: float,
    ) -> None:
        self._records[run_id] = {
            "analysis_run_id": run_id,
            "case_id": case_id,
            "status": status,
            "duration_ms": max(0, duration_ms),
            "tool_call_count": tool_call_count,
            "retrieval_call_count": retrieval_call_count,
            "estimated_tokens": estimated_tokens,
            "estimated_cost_cny": round(estimated_cost_cny, 6),
        }
        record_analysis = getattr(self._exporter, "record_analysis", None)
        if callable(record_analysis):
            record_analysis(
                status=status,
                provider=self._provider,
                model=self._model,
                duration_ms=duration_ms,
                tool_call_count=tool_call_count,
                retrieval_call_count=retrieval_call_count,
                estimated_tokens=estimated_tokens,
                estimated_cost_cny=estimated_cost_cny,
            )

    def list(self) -> list[dict[str, object]]:
        return [self._records[key] for key in sorted(self._records)]


@dataclass(frozen=True, slots=True)
class RetryAuditRecord:
    event_id: str
    consumer_group: str
    operator_id: str
    requested_at: datetime
    previous_state: str
    resulting_state: str
    attempts: int

    def as_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "consumer_group": self.consumer_group,
            "operator_id": self.operator_id,
            "requested_at": self.requested_at.isoformat(),
            "previous_state": self.previous_state,
            "resulting_state": self.resulting_state,
            "attempts": self.attempts,
        }
