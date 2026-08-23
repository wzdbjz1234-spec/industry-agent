"""Registry for EfficientAD and future anomlib visual scheme adapters."""

from __future__ import annotations

from collections.abc import Iterable

from .types import VisionDetector


class VisionSchemeRegistry:
    """Resolve a small named scheme to a detector implementation."""

    def __init__(self, detectors: Iterable[tuple[str, VisionDetector]] = ()) -> None:
        self._detectors: dict[str, VisionDetector] = {}
        for name, detector in detectors:
            self.register(name, detector)

    def register(self, name: str, detector: VisionDetector) -> None:
        normalized = name.strip()
        if not normalized:
            raise ValueError("visual scheme name cannot be empty")
        self._detectors[normalized] = detector

    def resolve(self, name: str) -> VisionDetector:
        try:
            return self._detectors[name]
        except KeyError as exc:
            available = ", ".join(self.names()) or "none"
            raise KeyError(f"visual scheme '{name}' is not registered; available: {available}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._detectors))

