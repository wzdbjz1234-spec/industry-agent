"""Deep module for continuous visual inspection and event recording."""

from .events import InMemoryVisionEventStore
from .registry import VisionSchemeRegistry
from .service import VisionProcessingError, VisionProcessingResult, VisionProcessingService
from .stream import VisionStreamWorker
from .types import VisionFrame, VisionPrediction

__all__ = [
    "InMemoryVisionEventStore",
    "VisionFrame",
    "VisionPrediction",
    "VisionProcessingError",
    "VisionProcessingResult",
    "VisionProcessingService",
    "VisionSchemeRegistry",
    "VisionStreamWorker",
]
