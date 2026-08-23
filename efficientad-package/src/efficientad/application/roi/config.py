"""ROI 配置读写与校验。

迁移自 ``roi_mask.py``，兼容旧的 ``mask`` 单值字段与新的 ``masks`` 列表字段。
"""

from __future__ import annotations

import json
from pathlib import Path

Rect = tuple[int, int, int, int]


def load_roi_config(path: str | Path) -> tuple[Rect, list[Rect]]:
    """读取 ROI 配置，返回 (roi, masks)，roi 与 masks 均为 (x,y,w,h)。"""
    with Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)

    roi = tuple(map(int, data["roi"]))
    raw_masks = data.get("masks")
    if raw_masks is None:
        raw_mask = data.get("mask")
        raw_masks = [] if raw_mask is None else [raw_mask]
    masks = [tuple(map(int, mask)) for mask in raw_masks]
    return roi, masks


def save_roi_config(roi: Rect, masks: list[Rect], path: str | Path) -> None:
    payload = {
        "roi": list(map(int, roi)),
        "masks": [list(map(int, mask)) for mask in masks],
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def validate_rect(rect, image_width: int, image_height: int, name: str) -> Rect:
    x, y, width, height = map(int, rect)
    if width <= 0 or height <= 0:
        raise ValueError(f"{name} 宽高必须为正: {rect}")
    if x < 0 or y < 0 or x + width > image_width or y + height > image_height:
        raise ValueError(f"{name} ({x},{y},{width},{height}) 超出图像 {image_width}x{image_height}")
    return x, y, width, height


__all__ = ["Rect", "load_roi_config", "save_roi_config", "validate_rect"]
