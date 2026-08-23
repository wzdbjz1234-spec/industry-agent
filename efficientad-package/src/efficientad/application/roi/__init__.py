"""ROI 包：配置、固定 ROI、ORB 匹配与统一处理器接口。"""

from .config import load_roi_config, save_roi_config
from .fixed import FixedROIProcessor
from .orb import ORBROIProcessor
from .processor import ROIBoundsError, ROIConfigError, ROIMatchError, ROIProcessor
from .types import ROICropResult

__all__ = [
    "FixedROIProcessor",
    "ORBROIProcessor",
    "ROIBoundsError",
    "ROIConfigError",
    "ROICropResult",
    "ROIMatchError",
    "ROIProcessor",
    "load_roi_config",
    "save_roi_config",
]
