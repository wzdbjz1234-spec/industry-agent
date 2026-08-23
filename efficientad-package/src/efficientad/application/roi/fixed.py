"""固定坐标 ROI 处理器（固定机位场景，不需要 ORB 特征匹配）。

迁移自 ``fixed_roi_crop.py::crop_fixed_roi`` + ``roi_mask.apply_masks``。
"""

from __future__ import annotations

import numpy as np

from .config import Rect, validate_rect
from .processor import ROIBoundsError
from .types import IMAGENET_MEAN_BGR, ROICropResult


def apply_masks(image: np.ndarray, masks) -> np.ndarray:
    """把每个掩膜矩形填充为中性 BGR 值，返回副本（与 roi_mask.apply_masks 一致）。"""
    result = image.copy()
    image_height, image_width = result.shape[:2]
    for mask in masks:
        x, y, width, height = validate_rect(mask, image_width, image_height, "Mask")
        channels = result.shape[2]
        value = IMAGENET_MEAN_BGR[:channels]
        if len(value) < channels:
            value = value + (255,) * (channels - len(value))
        result[y : y + height, x : x + width] = value
    return result


def _rect_corners(rect: Rect) -> np.ndarray:
    x, y, w, h = rect
    return np.array(
        [[x, y], [x + w, y], [x + w, y + h], [x, y + h]], dtype=np.float32
    )


class FixedROIProcessor:
    """按固定坐标 (x, y, w, h) 裁剪并应用掩膜。"""

    def __init__(self, roi: Rect, masks: list[Rect] | tuple[Rect, ...] = ()) -> None:
        self.roi = tuple(map(int, roi))
        self.masks = tuple(tuple(map(int, mask)) for mask in masks)

    def crop(self, image: np.ndarray) -> ROICropResult:
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError(f"输入必须是 (H, W, 3) BGR 数组, 实际 {image.shape}")
        height, width = image.shape[:2]
        x, y, w, h = self.roi
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > width or y + h > height:
            raise ROIBoundsError(f"ROI {self.roi} 超出图像 {width}x{height}")
        cropped = image[y : y + h, x : x + w].copy()
        cropped = apply_masks(cropped, self.masks)
        return ROICropResult(
            image=cropped,
            corners=_rect_corners(self.roi),
            rect=self.roi,
            masks=self.masks,
        )


__all__ = ["FixedROIProcessor", "apply_masks"]
