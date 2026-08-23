"""Continuous visual input, fault events, and NG fluctuation tests."""

import time
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from quality_case_agent.adapters.in_memory.stores import InMemoryInspectionStore
from quality_case_agent.adapters.vision.anomlib import AnomlibVisionAdapter
from quality_case_agent.application.ingestion.service import InspectionIngestionService
from quality_case_agent.application.vision import (
    InMemoryVisionEventStore,
    VisionFrame,
    VisionPrediction,
    VisionProcessingError,
    VisionProcessingService,
    VisionSchemeRegistry,
    VisionStreamWorker,
)


class FakeDetector:
    detector_type = "fake-vision"
    model_version = "fake-v1"
    adapter_version = "fake-adapter-v1"

    def __init__(self, is_ng: bool = False) -> None:
        self.is_ng = is_ng

    def predict(self, frame: VisionFrame) -> VisionPrediction:
        return VisionPrediction(
            anomaly_score=0.8 if self.is_ng else 0.05,
            threshold=0.2,
            is_ng=self.is_ng,
            detector_type=self.detector_type,
            model_version=self.model_version,
            adapter_version=self.adapter_version,
        )


def _frame(index: int, *, is_ng: bool = False) -> VisionFrame:
    return VisionFrame(
        frame_id=f"frame-{index}",
        inspected_at=datetime(2026, 8, 23, 3, 0, index, tzinfo=UTC),
        factory_id="factory-01",
        line_id="line-01",
        station_id="camera-01",
        product_id="part-A",
        unit_id=f"unit-{index}",
        batch_id="batch-01",
        image=b"not-used-by-fake",
        scheme="fake",
        metadata={"expected_ng": is_ng},
    )


def test_vision_service_records_fault_and_ng_rate_fluctuation() -> None:
    registry = VisionSchemeRegistry([("fake", FakeDetector())])
    events = InMemoryVisionEventStore()
    service = VisionProcessingService(
        registry,
        InspectionIngestionService(InMemoryInspectionStore()),
        events,
    )

    for index in range(3):
        service.process(_frame(index, is_ng=False))
    for index in range(3, 6):
        registry.register("fake", FakeDetector(is_ng=True))
        service.process(_frame(index, is_ng=True))

    event_types = [event.event_type for event in events.list_events()]
    assert "quality.vision.fault.v1" in event_types
    assert "quality.vision.ng-rate-fluctuation.v1" in event_types
    fluctuation = next(
        event for event in events.list_events() if event.event_type == "quality.vision.ng-rate-fluctuation.v1"
    )
    assert fluctuation.direction == "RISING"
    assert fluctuation.recent_ng_rate == 1.0


def test_anomlib_adapter_normalizes_mapping_result() -> None:
    adapter = AnomlibVisionAdapter(
        lambda image: {"score": 0.7, "threshold": 0.5, "defect_type": "scratch"},
        scheme_name="demo-scheme",
        model_version="anomlib-v1",
        threshold=0.5,
    )
    prediction = adapter.predict(_frame(1))
    assert prediction.detector_type == "anomlib:demo-scheme"
    assert prediction.is_ng is True
    assert prediction.defect_type == "scratch"


def test_processing_failure_is_recorded_and_redacted() -> None:
    class BrokenDetector(FakeDetector):
        def predict(self, frame: VisionFrame) -> VisionPrediction:
            raise RuntimeError("inference timeout token=secret-value")

    events = InMemoryVisionEventStore()
    service = VisionProcessingService(
        VisionSchemeRegistry([("broken", BrokenDetector())]),
        InspectionIngestionService(InMemoryInspectionStore()),
        events,
    )
    broken = _frame(1)
    broken = replace(broken, scheme="broken")
    with pytest.raises(VisionProcessingError):
        service.process(broken)
    event = events.list_events()[0]
    assert event.fault_kind == "PROCESSING_FAILURE"
    assert "secret-value" not in str(event.details)
    assert "[REDACTED]" in str(event.details)


def test_stream_worker_keeps_completed_job_state() -> None:
    service = VisionProcessingService(
        VisionSchemeRegistry([("fake", FakeDetector())]),
        InspectionIngestionService(InMemoryInspectionStore()),
        InMemoryVisionEventStore(),
    )
    worker = VisionStreamWorker(service)
    submitted = worker.submit(_frame(1))
    try:
        deadline = time.monotonic() + 1.0
        completed = None
        while time.monotonic() < deadline:
            completed = worker.get(submitted.job_id)
            if completed is not None and completed.status == "COMPLETED":
                break
            time.sleep(0.01)
        assert completed is not None
        assert completed.status == "COMPLETED"
    finally:
        worker.stop()
