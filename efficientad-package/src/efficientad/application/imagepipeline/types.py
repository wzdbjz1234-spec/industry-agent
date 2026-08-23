"""图像流水线核心数据类型（阶段 0 契约迁移）。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class PipelineResult:
    """ImagePipeline.process(image) 的返回值（仅内存对象，不落盘）。

    - ``loss`` / ``score`` / ``heatmap``: 汇总自模型输出的异常指标；
    - ``is_anomaly``: 构造流水线时给定 threshold 则为 score >= threshold 的
      判定结果，否则为 None；
    - ``roi_image`` / ``roi_corners``: ROI 裁剪图与四角，供可视化/叠加使用，
      流水线本身不保存这些内容。
    """

    loss: float
    score: float
    heatmap: np.ndarray
    is_anomaly: bool | None = None
    roi_image: np.ndarray | None = None
    roi_corners: np.ndarray | None = None

    def __post_init__(self) -> None:
        if self.heatmap.ndim != 2:
            raise ValueError(f"heatmap 必须是 (H, W), 实际 {self.heatmap.shape}")


__all__ = ["PipelineResult"]
