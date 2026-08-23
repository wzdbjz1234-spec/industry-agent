"""Adapter seam for visual schemes supplied by an optional anomlib package."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from typing import Any

from quality_case_agent.application.vision.types import VisionFrame, VisionPrediction


class AnomlibVisionAdapter:
    """Normalize an anomlib callable/object into the project's detector seam."""

    detector_type = "anomlib"
    adapter_version = "anomlib-input-v1"

    def __init__(
        self,
        scheme: Callable[[Any], object] | object,
        *,
        scheme_name: str,
        model_version: str,
        threshold: float,
    ) -> None:
        self.scheme = scheme
        self.scheme_name = scheme_name
        self.model_version = model_version
        self.threshold = threshold

    @classmethod
    def from_import_path(
        cls,
        import_path: str,
        *,
        scheme_name: str,
        model_version: str,
        threshold: float,
    ) -> AnomlibVisionAdapter:
        module_name, separator, attribute = import_path.partition(":")
        if not separator or not module_name or not attribute:
            raise ValueError("import_path must have the form module:attribute")
        scheme = getattr(importlib.import_module(module_name), attribute)
        if isinstance(scheme, type):
            scheme = scheme()
        return cls(
            scheme,
            scheme_name=scheme_name,
            model_version=model_version,
            threshold=threshold,
        )

    def predict(self, frame: VisionFrame) -> VisionPrediction:
        raw = self._invoke(frame.image)
        if isinstance(raw, VisionPrediction):
            return raw
        if not isinstance(raw, Mapping):
            raise TypeError("anomlib scheme must return VisionPrediction or a mapping")
        score = float(raw.get("anomaly_score", raw.get("score", 0.0)))
        threshold = float(raw.get("threshold", self.threshold))
        is_ng_value = raw.get("is_ng")
        is_ng = bool(is_ng_value) if is_ng_value is not None else score >= threshold
        return VisionPrediction(
            anomaly_score=score,
            threshold=threshold,
            is_ng=is_ng,
            detector_type=f"anomlib:{self.scheme_name}",
            model_version=self.model_version,
            adapter_version=self.adapter_version,
            defect_type=str(raw["defect_type"]) if raw.get("defect_type") is not None else None,
            anomaly_map_uri=(str(raw["anomaly_map_uri"]) if raw.get("anomaly_map_uri") else None),
            metadata={
                str(key): value
                for key, value in raw.items()
                if isinstance(value, (str, int, float, bool))
            },
        )

    def _invoke(self, image: object) -> object:
        if callable(self.scheme):
            return self.scheme(image)
        for method_name in ("predict", "infer", "detect"):
            method = getattr(self.scheme, method_name, None)
            if callable(method):
                return method(image)
        raise TypeError("anomlib scheme must be callable or expose predict/infer/detect")
