"""Composition-root helpers for durable resources.

Application services depend on ports; this module is the only place where a
deployment chooses SQLAlchemy/MinIO/Redis adapters.  The demo API intentionally
continues to use in-memory adapters, while production entrypoints can call
``build_persistent_resources`` with an explicit runtime mode.
"""

from dataclasses import dataclass

from quality_case_agent.adapters.postgres.monitoring import SqlAlchemyMonitoringBaselineStore
from quality_case_agent.adapters.postgres.repositories import (
    SqlAlchemyAnalysisRunStore,
    SqlAlchemyInboxStore,
    SqlAlchemyInspectionStore,
    SqlAlchemyMetricsStore,
    SqlAlchemyOutboxStore,
    SqlAlchemyPersistence,
    SqlAlchemyQualityCaseStore,
)
from quality_case_agent.config import RuntimeSettings


@dataclass(frozen=True, slots=True)
class PersistentResources:
    database: SqlAlchemyPersistence
    inspection: SqlAlchemyInspectionStore
    metrics: SqlAlchemyMetricsStore
    cases: SqlAlchemyQualityCaseStore
    runs: SqlAlchemyAnalysisRunStore
    outbox: SqlAlchemyOutboxStore
    inbox: SqlAlchemyInboxStore
    monitoring_baselines: SqlAlchemyMonitoringBaselineStore


def build_persistent_resources(settings: RuntimeSettings | None = None) -> PersistentResources:
    """Create all durable stores and fail fast if the configured DB is unavailable."""

    resolved = settings or RuntimeSettings.from_env()
    database = SqlAlchemyPersistence(resolved.database_url)
    database.create_schema()
    return PersistentResources(
        database=database,
        inspection=SqlAlchemyInspectionStore(database),
        metrics=SqlAlchemyMetricsStore(database),
        cases=SqlAlchemyQualityCaseStore(database),
        runs=SqlAlchemyAnalysisRunStore(database),
        outbox=SqlAlchemyOutboxStore(database),
        inbox=SqlAlchemyInboxStore(database),
        monitoring_baselines=SqlAlchemyMonitoringBaselineStore(database),
    )
