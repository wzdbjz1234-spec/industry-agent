"""模型包核心数据类型（阶段 0 契约迁移）。

自根目录 ``contracts.py`` 迁入，字段语义与校验逻辑保持不变。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ModelPrediction:
    """单个模型（一个产品/机位的 Student+AE 或 Teacher+Student+AE）的推理结果。

    - ``loss``: 有效区域内原始异常差异图的平均值（分位数归一化之前），
      与训练过程的 loss_total 语义不同，二者不得混用。
    - ``score``: 归一化异常图在有效区域内的最大值，用于阈值判定。
    - ``heatmap``: 归一化异常图，float32，(H, W)，尺寸与模型输入
      （即 ROI 裁剪图）一致。
    - st_* / ae_*: 可选分解输出；teacher-free 模式下 st 相关字段为 None。
    """

    loss: float
    score: float
    heatmap: np.ndarray
    st_loss: float | None = None
    ae_loss: float | None = None
    st_score: float | None = None
    ae_score: float | None = None
    st_heatmap: np.ndarray | None = None
    ae_heatmap: np.ndarray | None = None

    def __post_init__(self) -> None:
        if self.heatmap.ndim != 2:
            raise ValueError(f"heatmap 必须是 (H, W), 实际 {self.heatmap.shape}")
        if self.heatmap.dtype != np.float32:
            raise ValueError(f"heatmap 必须是 float32, 实际 {self.heatmap.dtype}")


__all__ = ["ModelPrediction"]
