"""Normalize visual predictions into the existing inspection and Case pipeline."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from quality_case_agent.application.ingestion.service import (
    IngestionReceipt,
    InspectionIngestionService,
)
from quality_case_agent.contracts.inspection import (
    DetectorContract,
    InspectionResultBatchContract,
    InspectionResultContract,
)
from quality_case_agent.contracts.vision import (
    AnomlibDetectionRequestContract,
    NgRateFluctuationEventContract,
    VisionFaultEventContract,
)

from .events import InMemoryVisionEventStore, NgRateFluctuationTracker
from .registry import VisionSchemeRegistry
from .types import VisionFrame, VisionPrediction


@dataclass(frozen=True, slots=True)
class VisionProcessingResult:
    record: InspectionResultContract
    receipt: IngestionReceipt
    events: tuple[VisionFaultEventContract | NgRateFluctuationEventContract, ...]


class VisionProcessingService:
    """Deep module for visual inference, ingestion, and event recording."""

    def __init__(
        self,
        registry: VisionSchemeRegistry,
        ingestion: InspectionIngestionService,
        events: InMemoryVisionEventStore,
        *,
        fluctuation_tracker: NgRateFluctuationTracker | None = None,
        post_ingest: Callable[[InspectionResultBatchContract], None] | None = None,
    ) -> None:
        self.registry = registry
        self._ingestion = ingestion
        self.events = events
        self._fluctuation_tracker = fluctuation_tracker or NgRateFluctuationTracker()
        self._post_ingest = post_ingest

    def process(self, frame: VisionFrame) -> VisionProcessingResult:
        detector = self.registry.resolve(frame.scheme)
        try:
            prediction = detector.predict(frame)
        except Exception as exc:
            fault = self._processing_failure(frame, detector, exc)
            self.events.append(fault)
            raise VisionProcessingError(fault) from exc
        return self._persist_prediction(frame, prediction)

    def process_anomlib_detection(
        self, request: AnomlibDetectionRequestContract
    ) -> VisionProcessingResult:
        is_ng = request.is_ng if request.is_ng is not None else request.anomaly_score >= request.threshold
        prediction = VisionPrediction(
            anomaly_score=request.anomaly_score,
            threshold=request.threshold,
            is_ng=is_ng,
            detector_type=f"anomlib:{request.scheme}",
            model_version=request.detector_version,
            adapter_version=request.adapter_version,
            defect_type=request.defect_type,
            defect_region=request.defect_region,
            anomaly_map_uri=request.anomaly_map_uri,
            metadata=request.metadata,
        )
        frame = VisionFrame(
            frame_id=request.frame_id,
            inspected_at=request.inspected_at,
            factory_id=request.factory_id,
            line_id=request.line_id,
            station_id=request.station_id,
            product_id=request.product_id,
            unit_id=request.unit_id,
            batch_id=request.batch_id,
            image=None,
            scheme=f"anomlib:{request.scheme}",
            image_uri=request.image_uri,
            metadata=request.metadata,
        )
        return self._persist_prediction(frame, prediction)

    def _persist_prediction(self, frame: VisionFrame, prediction: VisionPrediction) -> VisionProcessingResult:
        record = InspectionResultContract(
            result_id=frame.frame_id,
            inspected_at=frame.inspected_at,
            factory_id=frame.factory_id,
            line_id=frame.line_id,
            station_id=frame.station_id,
            product_id=frame.product_id,
            unit_id=frame.unit_id,
            batch_id=frame.batch_id,
            is_ng=prediction.is_ng,
            anomaly_score=_bounded(prediction.anomaly_score),
            threshold=_bounded(prediction.threshold),
            defect_type=prediction.defect_type,
            defect_region=prediction.defect_region,
            image_uri=frame.image_uri,
            anomaly_map_uri=prediction.anomaly_map_uri,
            detector=DetectorContract(
                type=prediction.detector_type,
                model_version=prediction.model_version,
                adapter_version=prediction.adapter_version,
            ),
            metadata={**frame.metadata, **prediction.metadata, "vision_scheme": frame.scheme},
        )
        batch = InspectionResultBatchContract(
            batch_message_id=f"vision:{frame.frame_id}",
            producer_id=f"vision-worker:{prediction.detector_type}",
            produced_at=datetime.now(UTC),
            records=[record],
        )
        receipt = self._ingestion.submit_batch(batch)
        if self._post_ingest is not None:
            self._post_ingest(batch)
        recorded: list[VisionFaultEventContract | NgRateFluctuationEventContract] = []
        if prediction.is_ng:
            fault = VisionFaultEventContract(
                event_id=f"vision-fault:{frame.frame_id}",
                occurred_at=frame.inspected_at,
                trace_id=f"vision:{frame.frame_id}",
                frame_id=frame.frame_id,
                scope=frame.scope,
                fault_kind="NG_DETECTION",
                detector_type=prediction.detector_type,
                model_version=prediction.model_version,
                anomaly_score=_bounded(prediction.anomaly_score),
                threshold=_bounded(prediction.threshold),
                details={"defect_type": prediction.defect_type or "unknown"},
            )
            self.events.append(fault)
            recorded.append(fault)
        fluctuation = self._fluctuation_tracker.observe(
            scope_key=_scope_key(frame),
            scope=frame.scope,
            inspected_at=frame.inspected_at,
            is_ng=prediction.is_ng,
            trace_id=f"vision:{frame.frame_id}",
        )
        if fluctuation is not None:
            self.events.append(fluctuation)
            recorded.append(fluctuation)
        return VisionProcessingResult(record=record, receipt=receipt, events=tuple(recorded))

    @staticmethod
    def _processing_failure(frame: VisionFrame, detector: object, exc: Exception) -> VisionFaultEventContract:
        detector_type = str(getattr(detector, "detector_type", frame.scheme))
        model_version = str(getattr(detector, "model_version", "unknown"))
        message = re.sub(r"(?i)(token|secret|password)=\S+", r"\1=[REDACTED]", str(exc))
        return VisionFaultEventContract(
            event_id=f"vision-processing-failure:{frame.frame_id}",
            occurred_at=datetime.now(UTC),
            trace_id=f"vision:{frame.frame_id}",
            frame_id=frame.frame_id,
            scope=frame.scope,
            fault_kind="PROCESSING_FAILURE",
            detector_type=detector_type,
            model_version=model_version,
            details={"error_type": type(exc).__name__, "error": message[:500]},
        )


class VisionProcessingError(RuntimeError):
    def __init__(self, event: VisionFaultEventContract) -> None:
        super().__init__(event.details.get("error", "vision processing failed"))
        self.event = event


def _scope_key(frame: VisionFrame) -> str:
    return hashlib.sha1("|".join(frame.scope.values()).encode("utf-8")).hexdigest()[:16]


def _bounded(value: float) -> float:
    return min(1.0, max(0.0, float(value)))
