"""In-memory persistence adapters with database-like idempotency semantics."""

from collections.abc import Sequence

from quality_case_agent.domain.inspection.models import InspectionBatch, InspectionResult
from quality_case_agent.domain.quality_case.metrics import QualityMetricWindow
from quality_case_agent.domain.quality_case.models import QualityCase, QualityCaseEvent


class InMemoryInspectionStore:
    def __init__(self) -> None:
        self._batches: set[str] = set()
        self._results: dict[str, InspectionResult] = {}

    def insert_batch(self, batch: InspectionBatch) -> tuple[int, int]:
        if batch.batch_message_id in self._batches:
            return 0, len(batch.records)

        accepted = 0
        duplicates = 0
        for result in batch.records:
            if result.result_id in self._results:
                duplicates += 1
                continue
            self._results[result.result_id] = result
            accepted += 1
        self._batches.add(batch.batch_message_id)
        return accepted, duplicates

    def list_results(self) -> Sequence[InspectionResult]:
        return tuple(
            sorted(
                self._results.values(), key=lambda result: (result.inspected_at, result.result_id)
            )
        )

    @property
    def count(self) -> int:
        return len(self._results)


class InMemoryMetricsStore:
    def __init__(self) -> None:
        self._windows: dict[tuple[int, object, tuple[str, str, str, str]], QualityMetricWindow] = {}

    def upsert_windows(self, windows: Sequence[QualityMetricWindow]) -> int:
        for window in windows:
            key = (window.window_minutes, window.window_start, window.dimension_key)
            self._windows[key] = window
        return len(windows)

    def list_windows(self) -> Sequence[QualityMetricWindow]:
        return tuple(
            sorted(
                self._windows.values(),
                key=lambda window: (
                    window.window_minutes,
                    window.window_start,
                    window.dimension_key,
                ),
            )
        )


class InMemoryQualityCaseStore:
    def __init__(self) -> None:
        self._cases: dict[str, QualityCase] = {}
        self._events: dict[str, QualityCaseEvent] = {}

    def save_case(self, case: QualityCase) -> None:
        existing = self._cases.get(case.case_id)
        if existing is not None and existing.snapshot.snapshot_hash != case.snapshot.snapshot_hash:
            raise ValueError("Quality Case snapshots are immutable")
        if existing is not None:
            # A detector replay can reconstruct the same immutable Case from all
            # metric windows. Never let that fresh shell erase investigation,
            # approval, QMS, confirmation, or archive state.
            if case.case_status == "WAITING_INVESTIGATION" and existing.case_status != case.case_status:
                case.case_status = existing.case_status
            if case.episode_status == "ACTIVE" and existing.episode_status == "RECOVERED":
                case.episode_status = existing.episode_status
                case.recovered_at = existing.recovered_at
            for attribute in (
                "proposal_id",
                "qms_task_id",
                "qms_task_uri",
                "qms_task_status",
                "qms_external_system",
                "confirmation_id",
                "archive_uri",
            ):
                if getattr(case, attribute) is None:
                    setattr(case, attribute, getattr(existing, attribute))
            if case.archive_revision == 0:
                case.archive_revision = existing.archive_revision
        self._cases[case.case_id] = case

    def record_event(self, event: QualityCaseEvent) -> None:
        self._events.setdefault(event.event_id, event)

    def list_cases(self) -> Sequence[QualityCase]:
        return tuple(sorted(self._cases.values(), key=lambda case: (case.opened_at, case.case_id)))

    def get_case(self, case_id: str) -> QualityCase | None:
        return self._cases.get(case_id)

    @property
    def events(self) -> Sequence[QualityCaseEvent]:
        return tuple(sorted(self._events.values(), key=lambda event: event.occurred_at))
