"""ROI 处理器统一接口与异常类型。

ROI 定位失败、配置不存在、坐标越界、掩膜越界统一抛明确异常，不返回 None。
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from .types import ROICropResult


class ROIConfigError(Exception):
    """ROI 配置不存在或格式非法。"""


class ROIBoundsError(Exception):
    """ROI 或掩膜坐标越界。"""


class ROIMatchError(Exception):
    """ROI 定位失败（如 ORB 特征匹配失败、透视映射越界）。"""


class ROIProcessor(Protocol):
    """ROI 处理器协议：输入整幅图像(BGR)，输出裁剪结果。"""

    def crop(self, image: np.ndarray) -> ROICropResult: ...


__all__ = [
    "ROIBoundsError",
    "ROIConfigError",
    "ROIMatchError",
    "ROIProcessor",
]
