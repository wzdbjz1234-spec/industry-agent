"""ROI 包核心数据类型（阶段 0 契约迁移）。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# 掩膜填充用中性 BGR 值（≈ ImageNet 均值，归一化后接近 0）
IMAGENET_MEAN_BGR = (104, 116, 124)


@dataclass(frozen=True)
class ROICropResult:
    """ROI 定位与裁剪阶段的统一返回类型。

    - ``image``: 裁剪 + 掩膜处理后的图像，BGR，uint8，(H, W, 3)。
    - ``corners``: 原图坐标系四角 (4, 2) float32（左上、右上、右下、左下）。
    - ``rect``: corners 外接矩形 (x, y, w, h)，相对原图左上角。
    - ``masks``: 已应用的掩膜（坐标相对 ROI 左上角）。
    """

    image: np.ndarray
    corners: np.ndarray
    rect: tuple[int, int, int, int]
    masks: tuple[tuple[int, int, int, int], ...] = ()

    def __post_init__(self) -> None:
        if self.image.ndim != 3 or self.image.shape[2] != 3:
            raise ValueError(f"ROI 图像必须是 (H, W, 3) BGR 数组, 实际 {self.image.shape}")
        if self.corners.shape != (4, 2):
            raise ValueError(f"corners 必须是 (4, 2), 实际 {self.corners.shape}")
        x, y, w, h = self.rect
        if w <= 0 or h <= 0:
            raise ValueError(f"rect 宽高必须为正, 实际 {self.rect}")


def valid_mask_from_masks(height: int, width: int, masks) -> np.ndarray:
    """由掩膜矩形生成 (H,W) uint8 有效掩膜（1=参与，0=忽略），坐标相对 ROI。"""
    valid = np.ones((height, width), dtype=np.uint8)
    for mask in masks:
        x, y, w, h = map(int, mask)
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > width or y + h > height:
            raise ValueError(f"掩膜 ({x},{y},{w},{h}) 超出 ROI {width}x{height}")
        valid[y : y + h, x : x + w] = 0
    return valid


__all__ = ["IMAGENET_MEAN_BGR", "ROICropResult", "valid_mask_from_masks"]
