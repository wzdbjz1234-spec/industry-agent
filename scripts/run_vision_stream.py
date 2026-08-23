"""Continuously process a directory of images through the provided EfficientAD pipeline."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "efficientad-package" / "src"))

from quality_case_agent.adapters.in_memory.stores import InMemoryInspectionStore
from quality_case_agent.adapters.vision.efficientad import EfficientADImagePipelineAdapter
from quality_case_agent.application.ingestion.service import InspectionIngestionService
from quality_case_agent.application.vision import (
    InMemoryVisionEventStore,
    VisionFrame,
    VisionProcessingService,
    VisionSchemeRegistry,
    VisionStreamWorker,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=ROOT / "efficientad-package/mydataset/my_product_raw/test/broken",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=ROOT / "efficientad-package/output/30/trainings/mvtec_ad/111",
    )
    parser.add_argument("--roi", default="1418,564,173,196", help="x,y,width,height")
    parser.add_argument("--threshold", type=float, default=0.2)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-images", type=int, default=5)
    parser.add_argument("--interval-ms", type=int, default=0)
    args = parser.parse_args()

    roi = tuple(int(value.strip()) for value in args.roi.split(","))
    if len(roi) != 4:
        parser.error("--roi must be x,y,width,height")
    image_paths = sorted(
        path
        for path in args.input_dir.iterdir()
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
    )[: args.max_images]
    if not image_paths:
        parser.error(f"no image files found in {args.input_dir}")

    adapter = EfficientADImagePipelineAdapter.from_directory(
        args.model_dir,
        roi=roi,
        threshold=args.threshold,
        device=args.device,
    )
    event_store = InMemoryVisionEventStore()
    inspection_store = InMemoryInspectionStore()
    service = VisionProcessingService(
        VisionSchemeRegistry([("efficientad", adapter)]),
        InspectionIngestionService(inspection_store),
        event_store,
    )
    worker = VisionStreamWorker(service)
    submitted = []
    start = datetime.now(UTC)
    for index, image_path in enumerate(image_paths):
        frame = VisionFrame(
            frame_id=f"efficientad-stream-{index:04d}",
            inspected_at=start + timedelta(milliseconds=index),
            factory_id="factory-01",
            line_id="line-01",
            station_id="camera-01",
            product_id="part-A",
            unit_id=f"unit-{index:04d}",
            batch_id="vision-stream-demo",
            image=image_path,
            scheme="efficientad",
            image_uri=str(image_path),
        )
        submitted.append(worker.submit(frame))
        if args.interval_ms > 0:
            time.sleep(args.interval_ms / 1000)

    results = []
    deadline = time.monotonic() + max(30, len(submitted) * 15)
    while time.monotonic() < deadline:
        results = [worker.get(job.job_id) for job in submitted]
        if len(results) == len(submitted) and all(
            result is not None and result.status in {"COMPLETED", "FAILED"} for result in results
        ):
            break
        time.sleep(0.05)
    worker.stop()

    completed = [result for result in results if result is not None and result.status == "COMPLETED"]
    failed = [result for result in results if result is not None and result.status == "FAILED"]
    payload = {
        "mode": "continuous-image-stream",
        "scheme": "efficientad",
        "input_count": len(image_paths),
        "completed_count": len(completed),
        "failed_count": len(failed),
        "ng_count": sum(bool(result.is_ng) for result in completed),
        "events": [event.model_dump(mode="json") for event in event_store.list_events()],
        "jobs": [result.model_dump(mode="json") for result in results if result is not None],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if len(completed) == len(image_paths) else 1


if __name__ == "__main__":
    raise SystemExit(main())
