"""应用包：面向业务的能力（ROI 定位、图像推理流水线）。"""

from .imagepipeline import (
    DualImagePipeline,
    DualPipelineResult,
    DualROIConfig,
    DualROIResult,
    ImagePipeline,
    PipelineResult,
)
from .roi import (
    FixedROIProcessor,
    ORBROIProcessor,
    ROIBoundsError,
    ROIConfigError,
    ROICropResult,
    ROIMatchError,
)

__all__ = [
    "FixedROIProcessor",
    "DualImagePipeline",
    "DualPipelineResult",
    "DualROIConfig",
    "DualROIResult",
    "ImagePipeline",
    "ORBROIProcessor",
    "PipelineResult",
    "ROIBoundsError",
    "ROIConfigError",
    "ROICropResult",
    "ROIMatchError",
]
