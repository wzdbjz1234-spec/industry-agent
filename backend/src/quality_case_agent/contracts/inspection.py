"""Inspection result message and API contracts."""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .common import ContractModel, to_utc


class DefectRegionContract(ContractModel):
    """Normalized location of a detected defect."""

    x_normalized: float = Field(ge=0.0, le=1.0)
    y_normalized: float = Field(ge=0.0, le=1.0)
    area_ratio: float = Field(ge=0.0, le=1.0)
    region_label: str = Field(min_length=1, max_length=64)


class DetectorContract(ContractModel):
    """Detector provenance carried with each result."""

    type: str = Field(min_length=1, max_length=128)
    model_version: str = Field(min_length=1, max_length=128)
    adapter_version: str = Field(min_length=1, max_length=128)


class InspectionResultContract(ContractModel):
    """One inspection result in ``inspection.result.batch.v1``."""

    result_id: str = Field(min_length=1, max_length=128)
    inspected_at: datetime
    factory_id: str = Field(min_length=1, max_length=128)
    line_id: str = Field(min_length=1, max_length=128)
    station_id: str = Field(min_length=1, max_length=128)
    product_id: str = Field(min_length=1, max_length=128)
    unit_id: str = Field(min_length=1, max_length=128)
    batch_id: str = Field(min_length=1, max_length=128)
    is_ng: bool
    anomaly_score: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    defect_type: str | None = Field(default=None, max_length=128)
    defect_region: DefectRegionContract | None = None
    image_uri: str | None = Field(default=None, max_length=2048)
    anomaly_map_uri: str | None = Field(default=None, max_length=2048)
    detector: DetectorContract
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @field_validator("inspected_at")
    @classmethod
    def normalize_inspected_at(cls, value: datetime) -> datetime:
        return to_utc(value)


class InspectionResultBatchContract(ContractModel):
    """Versioned batch accepted from a detector or replay adapter."""

    schema_version: Literal["1.0"] = "1.0"
    batch_message_id: str = Field(min_length=1, max_length=128)
    producer_id: str = Field(min_length=1, max_length=128)
    produced_at: datetime
    records: list[InspectionResultContract] = Field(min_length=1, max_length=100)

    @field_validator("produced_at")
    @classmethod
    def normalize_produced_at(cls, value: datetime) -> datetime:
        return to_utc(value)

    @model_validator(mode="after")
    def result_ids_are_unique(self) -> "InspectionResultBatchContract":
        result_ids = [record.result_id for record in self.records]
        if len(result_ids) != len(set(result_ids)):
            raise ValueError("result_id must be unique within a batch")
        return self
