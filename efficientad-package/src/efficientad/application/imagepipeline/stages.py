"""流水线输入阶段：图像格式统一。

约定（REFACTOR_PLAN.md 阶段 0 执行记录）：
- ``ImageInput = Path | PIL.Image.Image | numpy.ndarray``；
- NumPy 数组为 **BGR**（uint8 HxWx3）；PIL 图像为 RGB；Path 按 BGR 解码；
- 内部统一为 BGR numpy 后交给下游 ROI 阶段。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Union

import cv2
import numpy as np

if TYPE_CHECKING:
    from PIL import Image

ImageInput = Union[Path, str, "Image", np.ndarray]

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def to_bgr(image: ImageInput) -> np.ndarray:
    """任意输入 → BGR uint8 (H,W,3)。不修改原对象。"""
    if isinstance(image, np.ndarray):
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError(f"NumPy 图像必须是 (H, W, 3), 实际 {image.shape}")
        return image
    if isinstance(image, (Path, str)):
        path = Path(image)
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError(f"不支持的图片扩展名: {path.suffix}")
        data = np.fromfile(path, dtype=np.uint8)
        decoded = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if decoded is None:
            raise ValueError(f"无法解码图片: {path}")
        return decoded
    if hasattr(image, "convert"):  # PIL.Image
        return cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    raise TypeError(f"不支持的图像输入类型: {type(image)!r}")


__all__ = ["ImageInput", "to_bgr"]
