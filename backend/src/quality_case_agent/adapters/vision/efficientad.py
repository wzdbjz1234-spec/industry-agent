"""Adapter around the repository's ``efficientad.application.imagepipeline``."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from quality_case_agent.application.vision.types import VisionFrame, VisionPrediction


class EfficientADDependencyError(RuntimeError):
    """Raised when the optional EfficientAD runtime is not installed."""


class EfficientADImagePipelineAdapter:
    """Use the provided EfficientAD ImagePipeline as one visual scheme."""

    detector_type = "efficientad"
    adapter_version = "efficientad-imagepipeline-v1"

    def __init__(self, pipeline: Any, *, model_version: str, threshold: float) -> None:
        self._pipeline = pipeline
        self.model_version = model_version
        self.threshold = float(threshold)

    @classmethod
    def from_directory(
        cls,
        model_dir: str | Path,
        *,
        roi: tuple[int, int, int, int],
        threshold: float,
        device: str = "cpu",
        model_version: str | None = None,
    ) -> EfficientADImagePipelineAdapter:
        try:
            from efficientad.application import (  # type: ignore[import-not-found]
                FixedROIProcessor,
                ImagePipeline,
            )
            from efficientad.model import (  # type: ignore[import-not-found]
                ModelArtifacts,
                ModelRunner,
            )
        except ModuleNotFoundError as exc:
            raise EfficientADDependencyError(
                "EfficientAD runtime is unavailable; install efficientad-package dependencies "
                "or run with efficientad-package/.venv"
            ) from exc
        artifacts = ModelArtifacts.from_directory(Path(model_dir))
        runner = ModelRunner.load(artifacts, device=device, teacher_free=True)
        pipeline = ImagePipeline(
            roi=FixedROIProcessor(roi),
            model=runner,
            threshold=threshold,
        )
        return cls(
            pipeline,
            model_version=model_version or str(Path(model_dir).name),
            threshold=threshold,
        )

    def predict(self, frame: VisionFrame) -> VisionPrediction:
        image = _decode_bytes(frame.image)
        result = self._pipeline.process(image)
        score = float(result.score)
        is_ng = bool(result.is_anomaly if result.is_anomaly is not None else score >= self.threshold)
        return VisionPrediction(
            anomaly_score=score,
            threshold=self.threshold,
            is_ng=is_ng,
            detector_type=self.detector_type,
            model_version=self.model_version,
            adapter_version=self.adapter_version,
            defect_type="efficientad_anomaly" if is_ng else None,
            metadata={"loss": float(result.loss)},
        )


def _decode_bytes(image: object) -> object:
    if not isinstance(image, (bytes, bytearray, memoryview)):
        return image
    try:
        from PIL import Image  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise EfficientADDependencyError("Pillow is required for base64 image input") from exc
    return Image.open(io.BytesIO(bytes(image))).convert("RGB")
