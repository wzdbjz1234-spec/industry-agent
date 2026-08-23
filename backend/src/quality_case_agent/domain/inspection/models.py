"""Pure inspection domain objects."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class DefectRegion:
    x_normalized: float
    y_normalized: float
    area_ratio: float
    region_label: str


@dataclass(frozen=True, slots=True)
class DetectorMetadata:
    detector_type: str
    model_version: str
    adapter_version: str


@dataclass(frozen=True, slots=True)
class InspectionResult:
    result_id: str
    inspected_at: datetime
    factory_id: str
    line_id: str
    station_id: str
    product_id: str
    unit_id: str
    batch_id: str
    is_ng: bool
    anomaly_score: float
    threshold: float
    defect_type: str | None
    defect_region: DefectRegion | None
    image_uri: str | None
    anomaly_map_uri: str | None
    detector: DetectorMetadata
    metadata: Mapping[str, str | int | float | bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def dimension_key(self) -> tuple[str, str, str, str]:
        return self.factory_id, self.line_id, self.station_id, self.product_id


@dataclass(frozen=True, slots=True)
class InspectionBatch:
    batch_message_id: str
    producer_id: str
    produced_at: datetime
    records: tuple[InspectionResult, ...]
