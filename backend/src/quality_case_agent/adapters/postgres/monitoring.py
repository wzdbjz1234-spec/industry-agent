"""SQLAlchemy adapter for immutable monitoring baselines."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import Column, String, Table, Text, insert, select, update

from quality_case_agent.adapters.postgres.repositories import SqlAlchemyPersistence, metadata
from quality_case_agent.domain.monitoring.models import Baseline, DimensionKey

monitoring_baselines = Table(
    "monitoring_baselines",
    metadata,
    Column("baseline_key", String(512), primary_key=True),
    Column("dimension_key", String(512), nullable=False),
    Column("model_version", String(128), nullable=False),
    Column("baseline_version", String(64), nullable=False),
    Column("payload", Text, nullable=False),
)


def _key(dimension_key: DimensionKey, model_version: str) -> str:
    return f"{json.dumps(dimension_key, separators=(',', ':'))}:{model_version}"


def _from_payload(payload: dict[str, Any]) -> Baseline:
    return Baseline(
        baseline_id=str(payload["baseline_id"]),
        baseline_version=str(payload["baseline_version"]),
        created_at=datetime.fromisoformat(str(payload["created_at"])),
        dimension_key=tuple(str(value) for value in payload["dimension_key"]),  # type: ignore[arg-type]
        model_version=str(payload["model_version"]),
        sample_count=int(payload["sample_count"]),
        window_count=int(payload["window_count"]),
        ng_rate_mean=float(payload["ng_rate_mean"]),
        ng_rate_std=float(payload["ng_rate_std"]),
        score_mean=float(payload["score_mean"]),
        score_std=float(payload["score_std"]),
        score_p95=float(payload["score_p95"]),
        score_histogram=tuple(float(value) for value in payload["score_histogram"]),
    )


class SqlAlchemyMonitoringBaselineStore:
    def __init__(self, persistence: SqlAlchemyPersistence) -> None:
        self._db = persistence
        metadata.create_all(self._db.engine)

    def save(self, baseline: Baseline) -> None:
        values = {
            "baseline_key": _key(baseline.dimension_key, baseline.model_version),
            "dimension_key": json.dumps(baseline.dimension_key, separators=(",", ":")),
            "model_version": baseline.model_version,
            "baseline_version": baseline.baseline_version,
            "payload": json.dumps(baseline.as_dict(), sort_keys=True, separators=(",", ":")),
        }
        with self._db.begin() as conn:
            existing = conn.execute(select(monitoring_baselines.c.baseline_key).where(
                monitoring_baselines.c.baseline_key == values["baseline_key"]
            )).first()
            if existing is None:
                conn.execute(insert(monitoring_baselines).values(**values))
            else:
                conn.execute(update(monitoring_baselines).where(
                    monitoring_baselines.c.baseline_key == values["baseline_key"]
                ).values(**values))

    def get(self, dimension_key: DimensionKey, model_version: str) -> Baseline | None:
        with self._db.engine.connect() as conn:
            row = conn.execute(select(monitoring_baselines.c.payload).where(
                monitoring_baselines.c.baseline_key == _key(dimension_key, model_version)
            )).first()
            return _from_payload(json.loads(row[0])) if row else None

    def list(self) -> Sequence[Baseline]:
        with self._db.engine.connect() as conn:
            rows = conn.execute(select(monitoring_baselines).order_by(
                monitoring_baselines.c.dimension_key,
                monitoring_baselines.c.model_version,
            )).mappings()
            return tuple(_from_payload(json.loads(row["payload"])) for row in rows)
