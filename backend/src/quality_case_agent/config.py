"""Explicit runtime configuration shared by API and worker composition roots."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

RuntimeMode = Literal["demo", "test", "production"]
DEFAULT_DATABASE_URL = "sqlite:///quality_case_agent.db"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_MINIO_ENDPOINT = "localhost:9000"
DEFAULT_MINIO_BUCKET = "quality-case"


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    mode: RuntimeMode = "demo"
    database_url: str = DEFAULT_DATABASE_URL
    redis_url: str = DEFAULT_REDIS_URL
    minio_endpoint: str = DEFAULT_MINIO_ENDPOINT
    minio_bucket: str = DEFAULT_MINIO_BUCKET
    otel_endpoint: str | None = None
    prometheus_enabled: bool = True

    @classmethod
    def from_env(cls) -> RuntimeSettings:
        mode = os.getenv("QUALITY_RUNTIME_MODE", "demo").strip().lower()
        if mode not in {"demo", "test", "production"}:
            raise ValueError("QUALITY_RUNTIME_MODE must be demo, test, or production")
        database_url = os.getenv("QUALITY_DATABASE_URL")
        if mode == "production" and not database_url:
            raise ValueError("QUALITY_DATABASE_URL is required in production mode")
        return cls(
            mode=mode,  # type: ignore[arg-type]
            database_url=database_url or DEFAULT_DATABASE_URL,
            redis_url=os.getenv("QUALITY_REDIS_URL", DEFAULT_REDIS_URL),
            minio_endpoint=os.getenv("QUALITY_MINIO_ENDPOINT", DEFAULT_MINIO_ENDPOINT),
            minio_bucket=os.getenv("QUALITY_MINIO_BUCKET", DEFAULT_MINIO_BUCKET),
            otel_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
            prometheus_enabled=os.getenv("QUALITY_PROMETHEUS_ENABLED", "true").lower()
            not in {"0", "false", "no"},
        )
