"""ImagePipeline：接收单张图像，返回内存中的 PipelineResult。

无副作用约束（REFACTOR_PLAN.md 第 5.2 节）：
- 不写图片 / CSV / JSON / 输出目录 / ROI 配置 / 归一化缓存；
- 不修改输入图像；
- 只返回内存结果对象。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from efficientad.model.predictor import ModelRunner
from efficientad.application.roi.processor import ROIProcessor
from efficientad.application.roi.types import ROICropResult, valid_mask_from_masks

from .stages import ImageInput, to_bgr
from .types import PipelineResult


class ImagePipeline:
    """深模块：ROI 定位 + 掩膜 + 模型推理，一步返回结果。

    ::

        pipeline = ImagePipeline(roi=roi_processor, model=model_runner, threshold=0.15)
        result = pipeline.process(image)
        result.loss / result.score / result.heatmap / result.is_anomaly
    """

    def __init__(
        self,
        roi: ROIProcessor,
        model: ModelRunner,
        *,
        threshold: float | None = None,
    ) -> None:
        self.roi = roi
        self.model = model
        self.threshold = None if threshold is None else float(threshold)

    def process(self, image: ImageInput) -> PipelineResult:
        bgr = to_bgr(image)

        # 阶段 1: ROI 定位与裁剪(含掩膜像素填充);失败抛明确异常
        roi_result = self.roi.crop(bgr)
        assert isinstance(roi_result, ROICropResult)

        # 阶段 2: 模型推理(loss/score/heatmap,有效区域统计)
        valid_mask = _build_valid_mask(roi_result)
        prediction = self.model.predict(roi_result.image, valid_mask=valid_mask)

        is_anomaly = (
            prediction.score >= self.threshold if self.threshold is not None else None
        )
        return PipelineResult(
            loss=prediction.loss,
            score=prediction.score,
            heatmap=prediction.heatmap,
            is_anomaly=is_anomaly,
            roi_image=roi_result.image,
            roi_corners=roi_result.corners,
        )


def _build_valid_mask(roi_result: ROICropResult) -> np.ndarray | None:
    """由 ROI 掩膜生成 (H,W) uint8 有效掩膜；无掩膜返回 None。"""
    if not roi_result.masks:
        return None
    height, width = roi_result.image.shape[:2]
    return valid_mask_from_masks(height, width, roi_result.masks)


__all__ = ["ImagePipeline"]
