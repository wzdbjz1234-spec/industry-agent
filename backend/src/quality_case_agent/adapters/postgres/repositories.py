"""SQLAlchemy durable adapters for the application ports.

The tables intentionally keep the domain snapshot as canonical JSON.  This keeps
the adapter deep: callers see domain objects and idempotency semantics, while the
physical representation can run unchanged on SQLite in CI and PostgreSQL in
production (``postgresql+psycopg://...``).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine

from quality_case_agent.application.ports.inspection import InspectionResultStore
from quality_case_agent.application.ports.investigation import AnalysisRunStore
from quality_case_agent.application.ports.metrics import QualityMetricsStore
from quality_case_agent.application.ports.quality_case import QualityCaseStore
from quality_case_agent.contracts.investigation import InvestigationOutputContract
from quality_case_agent.domain.inspection.models import (
    DefectRegion,
    DetectorMetadata,
    InspectionBatch,
    InspectionResult,
)
from quality_case_agent.domain.investigation.models import AnalysisRun
from quality_case_agent.domain.quality_case.metrics import QualityMetricWindow
from quality_case_agent.domain.quality_case.models import (
    QualityCase,
    QualityCaseEvent,
    QualityCaseSnapshot,
)


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _dt(value: str | datetime | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def _required_dt(value: str | datetime | None) -> datetime:
    parsed = _dt(value)
    if parsed is None:
        raise ValueError("persisted timestamp is required")
    return parsed


def _window_payload(window: QualityMetricWindow) -> dict[str, object]:
    return window.as_dict()


def _window_from_payload(payload: dict[str, Any]) -> QualityMetricWindow:
    return QualityMetricWindow(
        window_start=_required_dt(payload["window_start"]),
        window_minutes=int(payload["window_minutes"]),
        factory_id=str(payload["factory_id"]),
        line_id=str(payload["line_id"]),
        station_id=str(payload["station_id"]),
        product_id=str(payload["product_id"]),
        total_count=int(payload["total_count"]),
        ng_count=int(payload["ng_count"]),
        ng_rate=float(payload["ng_rate"]),
        score_mean=float(payload["score_mean"]),
        score_p95=float(payload["score_p95"]),
        region_counts=tuple(sorted((str(k), int(v)) for k, v in dict(payload["region_counts"]).items())),
        model_versions=tuple(str(v) for v in payload["model_versions"]),
        warnings=tuple(str(v) for v in payload["warnings"]),
    )


def _inspection_payload(result: InspectionResult) -> dict[str, object]:
    return {
        "result_id": result.result_id,
        "inspected_at": result.inspected_at.isoformat(),
        "factory_id": result.factory_id,
        "line_id": result.line_id,
        "station_id": result.station_id,
        "product_id": result.product_id,
        "unit_id": result.unit_id,
        "batch_id": result.batch_id,
        "is_ng": result.is_ng,
        "anomaly_score": result.anomaly_score,
        "threshold": result.threshold,
        "defect_type": result.defect_type,
        "defect_region": asdict(result.defect_region) if result.defect_region else None,
        "image_uri": result.image_uri,
        "anomaly_map_uri": result.anomaly_map_uri,
        "detector": asdict(result.detector),
        "metadata": dict(result.metadata),
    }


def _inspection_from_payload(payload: dict[str, Any]) -> InspectionResult:
    region = payload.get("defect_region")
    detector = payload["detector"]
    return InspectionResult(
        result_id=str(payload["result_id"]),
        inspected_at=_required_dt(payload["inspected_at"]),
        factory_id=str(payload["factory_id"]),
        line_id=str(payload["line_id"]),
        station_id=str(payload["station_id"]),
        product_id=str(payload["product_id"]),
        unit_id=str(payload["unit_id"]),
        batch_id=str(payload["batch_id"]),
        is_ng=bool(payload["is_ng"]),
        anomaly_score=float(payload["anomaly_score"]),
        threshold=float(payload["threshold"]),
        defect_type=payload.get("defect_type"),
        defect_region=DefectRegion(**region) if region else None,
        image_uri=payload.get("image_uri"),
        anomaly_map_uri=payload.get("anomaly_map_uri"),
        detector=DetectorMetadata(**detector),
        metadata=dict(payload.get("metadata", {})),
    )


def _case_payload(case: QualityCase) -> dict[str, object]:
    return {
        "case_id": case.case_id,
        "fingerprint": case.fingerprint,
        "trigger_family": case.trigger_family,
        "opened_at": case.opened_at.isoformat(),
        "case_status": case.case_status,
        "episode_status": case.episode_status,
        "recovered_at": case.recovered_at.isoformat() if case.recovered_at else None,
        "proposal_id": case.proposal_id,
        "qms_task_id": case.qms_task_id,
        "qms_task_uri": case.qms_task_uri,
        "qms_task_status": case.qms_task_status,
        "qms_external_system": case.qms_external_system,
        "confirmation_id": case.confirmation_id,
        "archive_uri": case.archive_uri,
        "archive_revision": case.archive_revision,
        "snapshot": {
            "snapshot_id": case.snapshot.snapshot_id,
            "case_id": case.snapshot.case_id,
            "created_at": case.snapshot.created_at.isoformat(),
            "trigger_family": case.snapshot.trigger_family,
            "observations": [_window_payload(w) for w in case.snapshot.observations],
            "lookback_window_minutes": case.snapshot.lookback_window_minutes,
            "baseline_ng_rate": case.snapshot.baseline_ng_rate,
            "baseline_score_mean": case.snapshot.baseline_score_mean,
            "data_quality_warnings": list(case.snapshot.data_quality_warnings),
        },
        "snapshot_hash": case.snapshot.snapshot_hash,
    }


def _case_from_payload(payload: dict[str, Any]) -> QualityCase:
    snapshot = payload["snapshot"]
    snap = QualityCaseSnapshot(
        snapshot_id=str(snapshot["snapshot_id"]),
        case_id=str(snapshot["case_id"]),
        created_at=_required_dt(snapshot["created_at"]),
        trigger_family=str(snapshot["trigger_family"]),
        observations=tuple(_window_from_payload(w) for w in snapshot["observations"]),
        lookback_window_minutes=int(snapshot["lookback_window_minutes"]),
        baseline_ng_rate=float(snapshot["baseline_ng_rate"]),
        baseline_score_mean=float(snapshot["baseline_score_mean"]),
        data_quality_warnings=tuple(str(v) for v in snapshot["data_quality_warnings"]),
    )
    if snap.snapshot_hash != payload["snapshot_hash"]:
        raise ValueError("persisted snapshot hash does not match its canonical payload")
    return QualityCase(
        case_id=str(payload["case_id"]),
        fingerprint=str(payload["fingerprint"]),
        trigger_family=str(payload["trigger_family"]),
        opened_at=_required_dt(payload["opened_at"]),
        snapshot=snap,
        case_status=payload["case_status"],
        episode_status=payload["episode_status"],
        recovered_at=_dt(payload.get("recovered_at")),
        proposal_id=payload.get("proposal_id"),
        qms_task_id=payload.get("qms_task_id"),
        qms_task_uri=payload.get("qms_task_uri"),
        qms_task_status=payload.get("qms_task_status"),
        qms_external_system=payload.get("qms_external_system"),
        confirmation_id=payload.get("confirmation_id"),
        archive_uri=payload.get("archive_uri"),
        archive_revision=int(payload.get("archive_revision", 0)),
    )


metadata = MetaData()
inspection_batches = Table(
    "inspection_batches", metadata,
    Column("batch_message_id", String(128), primary_key=True),
    Column("producer_id", String(128), nullable=False),
    Column("produced_at", DateTime(timezone=True), nullable=False),
)
inspection_results = Table(
    "inspection_results", metadata,
    Column("result_id", String(128), primary_key=True),
    Column("batch_message_id", String(128), nullable=False),
    Column("inspected_at", DateTime(timezone=True), nullable=False),
    Column("payload", Text, nullable=False),
)
metric_windows = Table(
    "metric_windows", metadata,
    Column("window_minutes", Integer, primary_key=True),
    Column("window_start", String(64), primary_key=True),
    Column("dimension_key", String(512), primary_key=True),
    Column("payload", Text, nullable=False),
)
quality_cases = Table(
    "quality_cases", metadata,
    Column("case_id", String(128), primary_key=True),
    Column("snapshot_hash", String(64), nullable=False),
    Column("opened_at", DateTime(timezone=True), nullable=False),
    Column("payload", Text, nullable=False),
)
quality_case_events = Table(
    "quality_case_events", metadata,
    Column("event_id", String(256), primary_key=True),
    Column("case_id", String(128), nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("payload", Text, nullable=False),
)
analysis_runs = Table(
    "analysis_runs", metadata,
    Column("analysis_run_id", String(128), primary_key=True),
    Column("idempotency_key", String(256), unique=True, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("payload", Text, nullable=False),
    Column("output", Text, nullable=True),
)
outbox_events = Table(
    "outbox_events", metadata,
    Column("event_id", String(256), primary_key=True),
    Column("event_type", String(256), nullable=False),
    Column("aggregate_id", String(128), nullable=True),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("payload", Text, nullable=False),
    Column("published_at", DateTime(timezone=True), nullable=True),
)
inbox_events = Table(
    "inbox_events", metadata,
    Column("consumer_group", String(128), primary_key=True),
    Column("event_id", String(256), primary_key=True),
    Column("processed_at", DateTime(timezone=True), nullable=False),
)


class SqlAlchemyPersistence:
    """Engine and schema boundary shared by all durable adapters."""

    def __init__(self, url: str = "sqlite:///quality_case_agent.db") -> None:
        self.engine: Engine = create_engine(url, future=True)

    def create_schema(self) -> None:
        metadata.create_all(self.engine)

    def begin(self) -> Any:
        return self.engine.begin()


class SqlAlchemyInspectionStore(InspectionResultStore):
    def __init__(self, persistence: SqlAlchemyPersistence) -> None:
        self._db = persistence
        self._db.create_schema()

    def insert_batch(self, batch: InspectionBatch) -> tuple[int, int]:
        accepted = duplicates = 0
        with self._db.begin() as conn:
            if conn.execute(select(inspection_batches.c.batch_message_id).where(
                inspection_batches.c.batch_message_id == batch.batch_message_id
            )).first() is not None:
                return 0, len(batch.records)
            conn.execute(insert(inspection_batches).values(
                batch_message_id=batch.batch_message_id,
                producer_id=batch.producer_id,
                produced_at=batch.produced_at,
            ))
            for result in batch.records:
                exists = conn.execute(select(inspection_results.c.result_id).where(
                    inspection_results.c.result_id == result.result_id
                )).first()
                if exists is not None:
                    duplicates += 1
                    continue
                conn.execute(insert(inspection_results).values(
                    result_id=result.result_id,
                    batch_message_id=batch.batch_message_id,
                    inspected_at=result.inspected_at,
                    payload=_json(_inspection_payload(result)),
                ))
                accepted += 1
        return accepted, duplicates

    def list_results(self) -> Sequence[InspectionResult]:
        with self._db.engine.connect() as conn:
            rows = conn.execute(select(inspection_results).order_by(
                inspection_results.c.inspected_at, inspection_results.c.result_id
            )).mappings()
            return tuple(_inspection_from_payload(json.loads(row["payload"])) for row in rows)

    @property
    def count(self) -> int:
        with self._db.engine.connect() as conn:
            return len(conn.execute(select(inspection_results.c.result_id)).all())


class SqlAlchemyMetricsStore(QualityMetricsStore):
    def __init__(self, persistence: SqlAlchemyPersistence) -> None:
        self._db = persistence
        self._db.create_schema()

    def upsert_windows(self, windows: Sequence[QualityMetricWindow]) -> int:
        with self._db.begin() as conn:
            for window in windows:
                key = {
                    "window_minutes": window.window_minutes,
                    "window_start": window.window_start.isoformat(),
                    "dimension_key": _json(window.dimension_key),
                }
                payload = _json(_window_payload(window))
                exists = conn.execute(select(metric_windows.c.window_minutes).where(
                    metric_windows.c.window_minutes == key["window_minutes"],
                    metric_windows.c.window_start == key["window_start"],
                    metric_windows.c.dimension_key == key["dimension_key"],
                )).first()
                if exists is None:
                    conn.execute(insert(metric_windows).values(**key, payload=payload))
                else:
                    conn.execute(update(metric_windows).where(
                        metric_windows.c.window_minutes == key["window_minutes"],
                        metric_windows.c.window_start == key["window_start"],
                        metric_windows.c.dimension_key == key["dimension_key"],
                    ).values(payload=payload))
        return len(windows)

    def list_windows(self) -> Sequence[QualityMetricWindow]:
        with self._db.engine.connect() as conn:
            rows = conn.execute(select(metric_windows).order_by(
                metric_windows.c.window_minutes,
                metric_windows.c.window_start,
                metric_windows.c.dimension_key,
            )).mappings()
            return tuple(_window_from_payload(json.loads(row["payload"])) for row in rows)


class SqlAlchemyQualityCaseStore(QualityCaseStore):
    def __init__(self, persistence: SqlAlchemyPersistence) -> None:
        self._db = persistence
        self._db.create_schema()

    def save_case(self, case: QualityCase) -> None:
        payload = _case_payload(case)
        with self._db.begin() as conn:
            row = conn.execute(select(quality_cases).where(
                quality_cases.c.case_id == case.case_id
            )).mappings().first()
            if row is not None:
                existing = _case_from_payload(json.loads(row["payload"]))
                if existing.snapshot.snapshot_hash != case.snapshot.snapshot_hash:
                    raise ValueError("Quality Case snapshots are immutable")
                if case.case_status == "WAITING_INVESTIGATION" and existing.case_status != case.case_status:
                    case.case_status = existing.case_status
                if case.episode_status == "ACTIVE" and existing.episode_status == "RECOVERED":
                    case.episode_status = existing.episode_status
                    case.recovered_at = existing.recovered_at
                for attribute in (
                    "proposal_id", "qms_task_id", "qms_task_uri", "qms_task_status",
                    "qms_external_system", "confirmation_id", "archive_uri",
                ):
                    if getattr(case, attribute) is None:
                        setattr(case, attribute, getattr(existing, attribute))
                if case.archive_revision == 0:
                    case.archive_revision = existing.archive_revision
                payload = _case_payload(case)
                conn.execute(update(quality_cases).where(
                    quality_cases.c.case_id == case.case_id
                ).values(snapshot_hash=case.snapshot.snapshot_hash, opened_at=case.opened_at,
                         payload=_json(payload)))
                return
            conn.execute(insert(quality_cases).values(
                case_id=case.case_id,
                snapshot_hash=case.snapshot.snapshot_hash,
                opened_at=case.opened_at,
                payload=_json(payload),
            ))

    def record_event(self, event: QualityCaseEvent) -> None:
        with self._db.begin() as conn:
            if conn.execute(select(quality_case_events.c.event_id).where(
                quality_case_events.c.event_id == event.event_id
            )).first() is None:
                conn.execute(insert(quality_case_events).values(
                    event_id=event.event_id,
                    case_id=event.case_id,
                    occurred_at=event.occurred_at,
                    payload=_json({
                        "event_type": event.event_type,
                        "case_id": event.case_id,
                        "occurred_at": event.occurred_at.isoformat(),
                        "snapshot_id": event.snapshot_id,
                    }),
                ))

    def list_cases(self) -> Sequence[QualityCase]:
        with self._db.engine.connect() as conn:
            rows = conn.execute(select(quality_cases).order_by(
                quality_cases.c.opened_at, quality_cases.c.case_id
            )).mappings()
            return tuple(_case_from_payload(json.loads(row["payload"])) for row in rows)

    def get_case(self, case_id: str) -> QualityCase | None:
        with self._db.engine.connect() as conn:
            row = conn.execute(select(quality_cases.c.payload).where(
                quality_cases.c.case_id == case_id
            )).first()
            return _case_from_payload(json.loads(row[0])) if row else None

    @property
    def events(self) -> Sequence[QualityCaseEvent]:
        with self._db.engine.connect() as conn:
            rows = conn.execute(select(quality_case_events).order_by(
                quality_case_events.c.occurred_at, quality_case_events.c.event_id
            )).mappings()
            return tuple(
                QualityCaseEvent(
                    event_type=payload["event_type"],
                    case_id=payload["case_id"],
                    occurred_at=_required_dt(payload["occurred_at"]),
                    snapshot_id=payload.get("snapshot_id"),
                )
                for row in rows
                for payload in [json.loads(row["payload"])]
            )


class SqlAlchemyAnalysisRunStore(AnalysisRunStore):
    def __init__(self, persistence: SqlAlchemyPersistence) -> None:
        self._db = persistence
        self._db.create_schema()

    @staticmethod
    def _run_payload(run: AnalysisRun) -> dict[str, object]:
        payload = asdict(run)
        payload["started_at"] = run.started_at.isoformat()
        payload["completed_at"] = run.completed_at.isoformat() if run.completed_at else None
        return payload

    @staticmethod
    def _run_from_payload(payload: dict[str, Any]) -> AnalysisRun:
        payload = dict(payload)
        payload["started_at"] = _dt(payload["started_at"])
        payload["completed_at"] = _dt(payload.get("completed_at"))
        return AnalysisRun(**payload)

    def get_by_idempotency_key(self, key: str) -> AnalysisRun | None:
        with self._db.engine.connect() as conn:
            row = conn.execute(select(analysis_runs.c.payload).where(
                analysis_runs.c.idempotency_key == key
            )).first()
            return self._run_from_payload(json.loads(row[0])) if row else None

    def get_run(self, analysis_run_id: str) -> AnalysisRun | None:
        with self._db.engine.connect() as conn:
            row = conn.execute(select(analysis_runs.c.payload).where(
                analysis_runs.c.analysis_run_id == analysis_run_id
            )).first()
            return self._run_from_payload(json.loads(row[0])) if row else None

    def save_run(self, run: AnalysisRun) -> None:
        payload = self._run_payload(run)
        with self._db.begin() as conn:
            row = conn.execute(select(analysis_runs).where(
                analysis_runs.c.analysis_run_id == run.analysis_run_id
            )).mappings().first()
            if row is not None and row["idempotency_key"] != run.idempotency_key:
                raise ValueError("analysis_run_id cannot be reused for a different idempotency key")
            values = {
                "analysis_run_id": run.analysis_run_id,
                "idempotency_key": run.idempotency_key,
                "started_at": run.started_at,
                "payload": _json(payload),
            }
            if row is None:
                conn.execute(insert(analysis_runs).values(**values))
            else:
                conn.execute(update(analysis_runs).where(
                    analysis_runs.c.analysis_run_id == run.analysis_run_id
                ).values(**values))

    def save_output(self, output: InvestigationOutputContract) -> None:
        run_id = output.analysis.analysis_run_id
        encoded = output.model_dump_json()
        with self._db.begin() as conn:
            existing = conn.execute(select(analysis_runs.c.output).where(
                analysis_runs.c.analysis_run_id == run_id
            )).first()
            if existing is None:
                raise KeyError(f"analysis run not found: {run_id}")
            if existing[0] is not None and json.loads(existing[0]) != json.loads(encoded):
                raise ValueError("Analysis Run output is immutable")
            conn.execute(update(analysis_runs).where(
                analysis_runs.c.analysis_run_id == run_id
            ).values(output=encoded))

    def get_output(self, analysis_run_id: str) -> InvestigationOutputContract | None:
        with self._db.engine.connect() as conn:
            row = conn.execute(select(analysis_runs.c.output).where(
                analysis_runs.c.analysis_run_id == analysis_run_id
            )).first()
            return InvestigationOutputContract.model_validate_json(row[0]) if row and row[0] else None

    def list_runs(self) -> Sequence[AnalysisRun]:
        with self._db.engine.connect() as conn:
            rows = conn.execute(select(analysis_runs).order_by(
                analysis_runs.c.started_at, analysis_runs.c.analysis_run_id
            )).mappings()
            return tuple(self._run_from_payload(json.loads(row["payload"])) for row in rows)


class SqlAlchemyOutboxStore:
    """Durable Outbox/Inbox primitives shared with the Phase 17 publisher."""

    def __init__(self, persistence: SqlAlchemyPersistence) -> None:
        self._db = persistence
        self._db.create_schema()

    def append(self, event_id: str, event_type: str, aggregate_id: str | None,
               occurred_at: datetime, payload: dict[str, object]) -> None:
        with self._db.begin() as conn:
            if conn.execute(select(outbox_events.c.event_id).where(
                outbox_events.c.event_id == event_id
            )).first() is None:
                conn.execute(insert(outbox_events).values(
                    event_id=event_id, event_type=event_type, aggregate_id=aggregate_id,
                    occurred_at=occurred_at, payload=_json(payload), published_at=None,
                ))

    def list_unpublished(self, limit: int = 100) -> tuple[dict[str, object], ...]:
        with self._db.engine.connect() as conn:
            rows = conn.execute(select(outbox_events).where(
                outbox_events.c.published_at.is_(None)
            ).order_by(outbox_events.c.occurred_at).limit(limit)).mappings()
            return tuple(dict(row) | {"payload": json.loads(row["payload"])} for row in rows)

    def mark_published(self, event_id: str, published_at: datetime) -> None:
        with self._db.begin() as conn:
            conn.execute(update(outbox_events).where(
                outbox_events.c.event_id == event_id
            ).values(published_at=published_at))

    def inbox_seen(self, consumer_group: str, event_id: str) -> bool:
        with self._db.engine.connect() as conn:
            return conn.execute(select(inbox_events.c.event_id).where(
                inbox_events.c.consumer_group == consumer_group,
                inbox_events.c.event_id == event_id,
            )).first() is not None

    def mark_inbox(self, consumer_group: str, event_id: str, processed_at: datetime) -> None:
        with self._db.begin() as conn:
            if not self.inbox_seen(consumer_group, event_id):
                conn.execute(insert(inbox_events).values(
                    consumer_group=consumer_group, event_id=event_id, processed_at=processed_at,
                ))


class SqlAlchemyInboxStore:
    """Adapter view matching the application InboxStore port."""

    def __init__(self, persistence: SqlAlchemyPersistence) -> None:
        self._outbox = SqlAlchemyOutboxStore(persistence)

    def seen(self, consumer_group: str, event_id: str) -> bool:
        return self._outbox.inbox_seen(consumer_group, event_id)

    def mark(self, consumer_group: str, event_id: str, processed_at: datetime) -> None:
        self._outbox.mark_inbox(consumer_group, event_id, processed_at)
