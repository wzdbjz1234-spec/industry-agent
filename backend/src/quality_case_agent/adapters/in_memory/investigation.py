"""Durable-in-process Analysis Run and event adapters for offline development."""

from __future__ import annotations

from collections.abc import Sequence

from quality_case_agent.contracts.investigation import InvestigationOutputContract
from quality_case_agent.domain.investigation.models import AnalysisRun


class InMemoryAnalysisRunStore:
    def __init__(self) -> None:
        self._runs: dict[str, AnalysisRun] = {}
        self._by_key: dict[str, str] = {}
        self._outputs: dict[str, InvestigationOutputContract] = {}

    def get_by_idempotency_key(self, key: str) -> AnalysisRun | None:
        run_id = self._by_key.get(key)
        return self._runs.get(run_id) if run_id is not None else None

    def get_run(self, analysis_run_id: str) -> AnalysisRun | None:
        return self._runs.get(analysis_run_id)

    def save_run(self, run: AnalysisRun) -> None:
        existing = self._runs.get(run.analysis_run_id)
        if existing is not None and existing.idempotency_key != run.idempotency_key:
            raise ValueError("analysis_run_id cannot be reused for a different idempotency key")
        self._runs[run.analysis_run_id] = run
        self._by_key[run.idempotency_key] = run.analysis_run_id

    def save_output(self, output: InvestigationOutputContract) -> None:
        run_id = output.analysis.analysis_run_id
        existing = self._outputs.get(run_id)
        if existing is not None and existing.model_dump(mode="json") != output.model_dump(mode="json"):
            raise ValueError("Analysis Run output is immutable")
        self._outputs[run_id] = output

    def get_output(self, analysis_run_id: str) -> InvestigationOutputContract | None:
        return self._outputs.get(analysis_run_id)

    def list_runs(self) -> Sequence[AnalysisRun]:
        return tuple(sorted(self._runs.values(), key=lambda run: (run.started_at, run.analysis_run_id)))


class InMemoryInvestigationEventPublisher:
    def __init__(self) -> None:
        self._events: dict[str, object] = {}

    def publish(self, event: object) -> None:
        event_id = getattr(event, "event_id", None)
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("published event must contain a non-empty event_id")
        existing = self._events.get(event_id)
        if existing is not None and existing != event:
            raise ValueError(f"event_id already contains different payload: {event_id}")
        self._events[event_id] = event

    def list_events(self) -> Sequence[object]:
        return tuple(self._events.values())
