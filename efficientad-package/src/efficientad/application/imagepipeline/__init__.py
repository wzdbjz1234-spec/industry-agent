"""图像流水线：单 ROI 与双 ROI 推理。"""

from .dual import DualImagePipeline, DualPipelineResult, DualROIConfig, DualROIResult
from .pipeline import ImagePipeline
from .types import PipelineResult

__all__ = [
    "DualImagePipeline",
    "DualPipelineResult",
    "DualROIConfig",
    "DualROIResult",
    "ImagePipeline",
    "PipelineResult",
]
