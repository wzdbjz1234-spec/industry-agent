"""Versioned monitoring read contracts for the API and WebUI."""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel, to_utc


class MonitoringSignalContract(ContractModel):
    signal_type: Literal["EWMA", "CUSUM", "PSI", "KS", "DATA_QUALITY"]
    statistic: float
    threshold: float
    severity: Literal["INFO", "WARNING", "HIGH", "CRITICAL"]
    message: str = Field(min_length=1, max_length=512)


class MonitoringDecisionContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    decision_id: str = Field(min_length=1, max_length=128)
    evaluated_at: datetime
    dimension_key: tuple[str, str, str, str]
    model_version: str
    window_start: datetime
    status: Literal[
        "NORMAL",
        "PROCESS_SHIFT",
        "MODEL_DRIFT",
        "DATA_QUALITY_BLOCK",
        "BASELINE_MISSING",
    ]
    severity: Literal["INFO", "WARNING", "HIGH", "CRITICAL"]
    action: Literal["NONE", "OPEN_CASE", "MERGE_CASE", "BLOCK"]
    baseline_version: str | None = None
    signals: list[MonitoringSignalContract] = Field(default_factory=list)
    data_quality_warnings: list[str] = Field(default_factory=list)
    cooldown_minutes: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def normalize_dates(self) -> "MonitoringDecisionContract":
        object.__setattr__(self, "evaluated_at", to_utc(self.evaluated_at))
        object.__setattr__(self, "window_start", to_utc(self.window_start))
        return self


class MonitoringReportContract(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    evaluated_at: datetime
    window_count: int = Field(ge=0)
    baseline_count: int = Field(ge=0)
    decisions: list[MonitoringDecisionContract] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_evaluated_at(self) -> "MonitoringReportContract":
        object.__setattr__(self, "evaluated_at", to_utc(self.evaluated_at))
        return self
