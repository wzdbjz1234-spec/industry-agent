"""Contracts for continuous visual inspection input and event recording."""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .common import ContractModel, to_utc
from .inspection import DefectRegionContract


class VisionFrameRequestContract(ContractModel):
    """A frame submitted to a registered visual detector."""

    schema_version: Literal["1.0"] = "1.0"
    frame_id: str = Field(min_length=1, max_length=128)
    inspected_at: datetime
    factory_id: str = Field(min_length=1, max_length=128)
    line_id: str = Field(min_length=1, max_length=128)
    station_id: str = Field(min_length=1, max_length=128)
    product_id: str = Field(min_length=1, max_length=128)
    unit_id: str = Field(min_length=1, max_length=128)
    batch_id: str = Field(min_length=1, max_length=128)
    scheme: str = Field(default="efficientad", min_length=1, max_length=128)
    image_path: str | None = Field(default=None, max_length=2048)
    image_base64: str | None = Field(default=None, max_length=16_000_000)
    image_uri: str | None = Field(default=None, max_length=2048)
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @field_validator("inspected_at")
    @classmethod
    def normalize_inspected_at(cls, value: datetime) -> datetime:
        return to_utc(value)

    @model_validator(mode="after")
    def require_image_payload(self) -> "VisionFrameRequestContract":
        if (self.image_path is None) == (self.image_base64 is None):
            raise ValueError("exactly one of image_path or image_base64 is required")
        return self


class AnomlibDetectionRequestContract(ContractModel):
    """Normalized output accepted from any anomlib visual scheme."""

    schema_version: Literal["1.0"] = "1.0"
    frame_id: str = Field(min_length=1, max_length=128)
    inspected_at: datetime
    factory_id: str = Field(min_length=1, max_length=128)
    line_id: str = Field(min_length=1, max_length=128)
    station_id: str = Field(min_length=1, max_length=128)
    product_id: str = Field(min_length=1, max_length=128)
    unit_id: str = Field(min_length=1, max_length=128)
    batch_id: str = Field(min_length=1, max_length=128)
    scheme: str = Field(default="anomlib", min_length=1, max_length=128)
    detector_version: str = Field(min_length=1, max_length=128)
    adapter_version: str = Field(default="anomlib-input-v1", min_length=1, max_length=128)
    anomaly_score: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    is_ng: bool | None = None
    defect_type: str | None = Field(default=None, max_length=128)
    defect_region: DefectRegionContract | None = None
    image_uri: str | None = Field(default=None, max_length=2048)
    anomaly_map_uri: str | None = Field(default=None, max_length=2048)
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @field_validator("inspected_at")
    @classmethod
    def normalize_inspected_at(cls, value: datetime) -> datetime:
        return to_utc(value)


class PublicDatasetReplayRequestContract(ContractModel):
    """Configuration for a deterministic public anomaly-dataset replay."""

    schema_version: Literal["1.0"] = "1.0"
    dataset: Literal["MVTec AD", "VisA", "BTAD"]
    category: str = Field(min_length=1, max_length=128)
    model: Literal["EfficientAD", "PatchCore", "PaDiM", "DRAEM"]
    seed: int = Field(default=7, ge=0, le=2_147_483_647)
    fps: int = Field(default=10, ge=1, le=60)


class VisionJobContract(ContractModel):
    """State and result of a frame submitted to the continuous worker."""

    schema_version: Literal["1.0"] = "1.0"
    job_id: str
    frame_id: str
    scheme: str
    status: Literal["QUEUED", "PROCESSING", "COMPLETED", "FAILED"]
    submitted_at: datetime
    completed_at: datetime | None = None
    result_id: str | None = None
    is_ng: bool | None = None
    anomaly_score: float | None = Field(default=None, ge=0.0, le=1.0)
    error: str | None = None


class VisionStatusContract(ContractModel):
    """Operational status of the continuous visual worker."""

    schema_version: Literal["1.0"] = "1.0"
    worker: Literal["vision-worker"] = "vision-worker"
    running: bool
    queued: int = Field(ge=0)
    completed: int = Field(ge=0)
    failed: int = Field(ge=0)
    registered_schemes: list[str]


class VisionFaultEventContract(ContractModel):
    """A detected NG frame or a visual processing failure."""

    schema_version: Literal["1.0"] = "1.0"
    event_id: str
    event_type: Literal["quality.vision.fault.v1"] = "quality.vision.fault.v1"
    occurred_at: datetime
    trace_id: str
    frame_id: str
    scope: dict[str, str]
    fault_kind: Literal["NG_DETECTION", "PROCESSING_FAILURE"]
    detector_type: str
    model_version: str
    anomaly_score: float | None = Field(default=None, ge=0.0, le=1.0)
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    details: dict[str, str | int | float | bool] = Field(default_factory=dict)


class NgRateFluctuationEventContract(ContractModel):
    """A statistically simple rolling-window NG rate fluctuation event."""

    schema_version: Literal["1.0"] = "1.0"
    event_id: str
    event_type: Literal["quality.vision.ng-rate-fluctuation.v1"] = (
        "quality.vision.ng-rate-fluctuation.v1"
    )
    occurred_at: datetime
    trace_id: str
    scope: dict[str, str]
    window_start: datetime
    window_end: datetime
    sample_count: int = Field(ge=1)
    baseline_ng_rate: float = Field(ge=0.0, le=1.0)
    recent_ng_rate: float = Field(ge=0.0, le=1.0)
    delta: float
    direction: Literal["RISING", "FALLING"]
    details: dict[str, str | int | float | bool] = Field(default_factory=dict)
