"""双 ROI、双模型的单图推理流水线。

这个模块把 UI 需要知道的内容压缩为两个接口：

* ``DualROIConfig``：一个模型产物目录 + 一个固定 ROI + 一个阈值；
* ``DualImagePipeline.process(image)``：返回两个 ROI 的裁剪图、热力图、
  loss、score 和判定结果。

流水线只在内存中处理图像，不保存结果；模型默认使用 teacher-free 模式，
即只加载 Student + Autoencoder。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from efficientad.model import ModelArtifacts, ModelRunner

from ..roi import FixedROIProcessor, load_roi_config
from .pipeline import ImagePipeline
from .stages import ImageInput, to_bgr

Rect = tuple[int, int, int, int]
AGGREGATION_POLICIES = ("any_anomaly", "all_anomaly", "highest_relative_score")


@dataclass(frozen=True)
class DualROIConfig:
    """一个 ROI 检测单元的配置。"""

    name: str
    model_dir: Path
    roi: Rect
    threshold: float
    masks: tuple[Rect, ...] = ()

    @classmethod
    def from_files(
        cls,
        *,
        name: str,
        model_dir: str | Path,
        roi_config: str | Path,
        threshold: float,
    ) -> "DualROIConfig":
        roi, masks = load_roi_config(roi_config)
        return cls(
            name=name,
            model_dir=Path(model_dir).expanduser().resolve(),
            roi=roi,
            threshold=float(threshold),
            masks=tuple(masks),
        )


@dataclass(frozen=True)
class DualROIResult:
    """一个 ROI 的完整检测结果。"""

    name: str
    model_dir: Path
    roi: Rect
    roi_image: np.ndarray
    heatmap: np.ndarray
    loss: float
    score: float
    threshold: float
    is_anomaly: bool


@dataclass(frozen=True)
class DualPipelineResult:
    """双 ROI 检测结果，不包含任何文件路径输出。"""

    image: np.ndarray
    rois: tuple[DualROIResult, ...]
    is_anomaly: bool

    @property
    def score(self) -> float:
        return max((item.score for item in self.rois), default=0.0)

    def aggregate(self, policy: str = "any_anomaly") -> tuple[bool, float]:
        """按 UI 选择的策略计算整体判定和最高相对阈值。"""

        if policy not in AGGREGATION_POLICIES:
            raise ValueError(f"未知整体判定策略: {policy}")
        if not self.rois:
            return False, 0.0
        ratios = [
            item.score / item.threshold if item.threshold > 0 else float("inf")
            for item in self.rois
        ]
        if policy == "all_anomaly":
            verdict = all(item.is_anomaly for item in self.rois)
        elif policy == "highest_relative_score":
            verdict = max(ratios) >= 1.0
        else:
            verdict = any(item.is_anomaly for item in self.rois)
        return verdict, max(ratios)


class DualImagePipeline:
    """加载两个 teacher-free 模型并对同一张原图执行两个 ROI 检测。"""

    def __init__(
        self,
        configs: Iterable[DualROIConfig],
        *,
        device: str = "auto",
    ) -> None:
        self.configs = tuple(configs)
        if len(self.configs) != 2:
            raise ValueError(f"DualImagePipeline 需要恰好两个 ROI，实际 {len(self.configs)} 个")
        self.device = device
        self._pipelines = tuple(self._build_pipeline(config) for config in self.configs)

    def _build_pipeline(self, config: DualROIConfig) -> ImagePipeline:
        artifacts = ModelArtifacts.from_directory(config.model_dir)
        runner = ModelRunner.load(
            artifacts,
            device=self.device,
            teacher_free=True,
            st_weight=0.0,
            ae_weight=1.0,
        )
        return ImagePipeline(
            roi=FixedROIProcessor(config.roi, config.masks),
            model=runner,
            threshold=config.threshold,
        )

    def process(self, image: ImageInput) -> DualPipelineResult:
        bgr = to_bgr(image)
        results: list[DualROIResult] = []
        for config, pipeline in zip(self.configs, self._pipelines):
            result = pipeline.process(bgr)
            if result.roi_image is None:
                raise RuntimeError(f"{config.name} 没有返回 ROI 图像")
            results.append(
                DualROIResult(
                    name=config.name,
                    model_dir=config.model_dir,
                    roi=config.roi,
                    roi_image=result.roi_image,
                    heatmap=result.heatmap,
                    loss=result.loss,
                    score=result.score,
                    threshold=config.threshold,
                    is_anomaly=bool(result.is_anomaly),
                )
            )
        frozen = tuple(results)
        return DualPipelineResult(
            image=bgr.copy(),
            rois=frozen,
            is_anomaly=any(item.is_anomaly for item in frozen),
        )


__all__ = [
    "AGGREGATION_POLICIES",
    "DualImagePipeline",
    "DualPipelineResult",
    "DualROIConfig",
    "DualROIResult",
]
