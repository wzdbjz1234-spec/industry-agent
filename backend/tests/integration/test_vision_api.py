"""HTTP acceptance tests for continuous vision input and anomlib results."""

import asyncio
from datetime import UTC, datetime

import httpx
from quality_case_agent.application.vision import VisionFrame, VisionPrediction
from quality_case_agent.entrypoints.api.app import build_demo_container, create_app


class ApiFakeDetector:
    detector_type = "api-fake"
    model_version = "api-fake-v1"
    adapter_version = "api-fake-adapter-v1"

    def predict(self, frame: VisionFrame) -> VisionPrediction:
        return VisionPrediction(
            anomaly_score=0.8,
            threshold=0.2,
            is_ng=True,
            detector_type=self.detector_type,
            model_version=self.model_version,
            adapter_version=self.adapter_version,
        )


def test_vision_frame_queue_and_anomlib_input_api() -> None:
    async def exercise() -> None:
        container = build_demo_container()
        container.vision_registry.register("api-fake", ApiFakeDetector())
        transport = httpx.ASGITransport(app=create_app(container))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            schemes = await client.get("/api/v1/vision/schemes")
            assert schemes.status_code == 200
            assert "api-fake" in schemes.json()["registered"]

            queued = await client.post(
                "/api/v1/vision/frames",
                json={
                    "frame_id": "api-frame-001",
                    "inspected_at": "2026-08-23T03:00:00Z",
                    "factory_id": "factory-01",
                    "line_id": "line-01",
                    "station_id": "camera-01",
                    "product_id": "part-A",
                    "unit_id": "unit-001",
                    "batch_id": "batch-01",
                    "scheme": "api-fake",
                    "image_base64": "aGVsbG8=",
                },
            )
            assert queued.status_code == 200
            job_id = queued.json()["job_id"]
            status = None
            for _ in range(20):
                status = await client.get(f"/api/v1/vision/jobs/{job_id}")
                if status.json()["status"] in {"COMPLETED", "FAILED"}:
                    break
                await asyncio.sleep(0.02)
            assert status is not None
            assert status.json()["status"] == "COMPLETED"
            assert status.json()["is_ng"] is True

            anomlib = await client.post(
                "/api/v1/vision/anomlib/detections",
                json={
                    "frame_id": "anomlib-frame-001",
                    "inspected_at": datetime.now(UTC).isoformat(),
                    "factory_id": "factory-01",
                    "line_id": "line-01",
                    "station_id": "camera-01",
                    "product_id": "part-A",
                    "unit_id": "unit-002",
                    "batch_id": "batch-01",
                    "scheme": "demo-scheme",
                    "detector_version": "anomlib-demo-v1",
                    "anomaly_score": 0.91,
                    "threshold": 0.5,
                    "defect_type": "scratch",
                },
            )
            assert anomlib.status_code == 200
            assert anomlib.json()["record"]["detector"]["type"] == "anomlib:demo-scheme"

            events = await client.get("/api/v1/vision/events")
            assert events.status_code == 200
            assert any(item["event_type"] == "quality.vision.fault.v1" for item in events.json())

            replay = await client.post(
                "/api/v1/demo/public-dataset-replay",
                json={
                    "dataset": "MVTec AD",
                    "category": "Hazelnut",
                    "model": "EfficientAD",
                    "seed": 7,
                    "fps": 10,
                },
            )
            assert replay.status_code == 200
            assert replay.json()["replay"]["frame_count"] == 70
            assert replay.json()["replay"]["normalized_contract"] == "inspection.result.batch.v1"
            assert replay.json()["case_ids"]

            missing_scheme = await client.post(
                "/api/v1/vision/frames",
                json={
                    "frame_id": "missing-scheme",
                    "inspected_at": "2026-08-23T03:00:00Z",
                    "factory_id": "factory-01",
                    "line_id": "line-01",
                    "station_id": "camera-01",
                    "product_id": "part-A",
                    "unit_id": "unit-003",
                    "batch_id": "batch-01",
                    "scheme": "not-registered",
                    "image_base64": "aGVsbG8=",
                },
            )
            assert missing_scheme.status_code == 503

    asyncio.run(exercise())
