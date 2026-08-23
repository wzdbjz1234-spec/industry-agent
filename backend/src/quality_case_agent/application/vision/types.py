"""Internal types at the visual detector seam."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from quality_case_agent.contracts.inspection import DefectRegionContract


@dataclass(frozen=True, slots=True)
class VisionFrame:
    """One image and its immutable inspection context."""

    frame_id: str
    inspected_at: datetime
    factory_id: str
    line_id: str
    station_id: str
    product_id: str
    unit_id: str
    batch_id: str
    image: Any
    scheme: str = "efficientad"
    image_uri: str | None = None
    metadata: Mapping[str, str | int | float | bool] = field(default_factory=dict)

    @property
    def scope(self) -> dict[str, str]:
        return {
            "factory_id": self.factory_id,
            "line_id": self.line_id,
            "station_id": self.station_id,
            "product_id": self.product_id,
        }


@dataclass(frozen=True, slots=True)
class VisionPrediction:
    """Normalized result returned by EfficientAD or an anomlib scheme."""

    anomaly_score: float
    threshold: float
    is_ng: bool
    detector_type: str
    model_version: str
    adapter_version: str
    defect_type: str | None = None
    defect_region: DefectRegionContract | None = None
    anomaly_map_uri: str | None = None
    metadata: Mapping[str, str | int | float | bool] = field(default_factory=dict)


class VisionDetector(Protocol):
    """Small seam implemented by each visual scheme."""

    detector_type: str
    model_version: str
    adapter_version: str

    def predict(self, frame: VisionFrame) -> VisionPrediction: ...


class AnomlibCallable(Protocol):
    """Callable shape accepted from an anomlib scheme."""

    def __call__(self, image: Any) -> VisionPrediction | Mapping[str, object]: ...
