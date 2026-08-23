"""模型运行器：接收 ROI 图像(BGR numpy)，返回 ModelPrediction。

迁移自 ``efficientad_tools/predictor.py`` 与 ``dual_detector.py`` 的前向逻辑：
- 预处理与 dual_detector 完全一致（cv2 BGR→RGB → PIL → torchvision 256x256 变换）；
- 评分与热力图计算走 ``scoring`` 纯函数；
- 归一化参数缺失时在 ``load`` 阶段直接抛错，不自动写缓存。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
import torch
from PIL import Image
from torch import nn
from torchvision import transforms

from . import scoring
from .artifacts import ModelArtifacts
from .loader import (
    load_models,
    load_normalization,
    load_valid_input_mask,
    resolve_device,
)
from .normalization import NormalizationParams
from .types import ModelPrediction

DEFAULT_IMAGE_SIZE = 256

_DEFAULT_TRANSFORM = transforms.Compose(
    [
        transforms.Resize((DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ]
)


def _to_input_tensor(bgr_image: np.ndarray, device: torch.device) -> torch.Tensor:
    """BGR (H,W,3) uint8 → [3,256,256] 归一化张量（批维由调用方 stack 添加）。"""
    rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
    return _DEFAULT_TRANSFORM(Image.fromarray(rgb)).to(device)


def _out_channels(module: nn.Module) -> int:
    last = module[-1] if isinstance(module, nn.Sequential) else module
    value = getattr(last, "out_channels", None) or getattr(last, "out_features", None)
    if value is None:
        raise ValueError(f"无法推断输出通道数: {module}")
    return int(value)


def _mask_to_tensor(valid_mask: np.ndarray | None, device: torch.device) -> torch.Tensor | None:
    """运行时有效掩膜(H,W, 1=有效) → [1,1,256,256] float32；None 则原样返回。"""
    if valid_mask is None:
        return None
    mask = np.asarray(valid_mask, dtype=np.float32) > 0
    return torch.from_numpy(mask.astype(np.float32))[None, None].to(device)


class ModelRunner:
    """单个产品/机位模型的推理封装。线程安全（eval 模式下无状态）。"""

    def __init__(
        self,
        *,
        teacher: nn.Module | None,
        student: nn.Module,
        autoencoder: nn.Module,
        normalization: NormalizationParams,
        device: torch.device,
        teacher_free: bool = True,
        st_weight: float = 0.0,
        ae_weight: float = 1.0,
        valid_input_mask: torch.Tensor | None = None,
    ) -> None:
        self.teacher = teacher
        self.student = student
        self.autoencoder = autoencoder
        self.normalization = normalization
        self.device = device
        self.teacher_free = teacher_free
        self.st_weight = float(st_weight)
        self.ae_weight = float(ae_weight)
        self.valid_input_mask = valid_input_mask

        teacher_channels = (
            _out_channels(teacher)
            if teacher is not None
            else _out_channels(student) - _out_channels(autoencoder)
        )
        self.teacher_channels = int(teacher_channels)
        self.ae_channels = int(_out_channels(autoencoder))

    # ── 工厂 ──────────────────────────────────────────────────────

    @classmethod
    def load(
        cls,
        artifacts: ModelArtifacts,
        *,
        device: str | torch.device = "auto",
        teacher_free: bool = True,
        st_weight: float = 0.0,
        ae_weight: float = 1.0,
    ) -> "ModelRunner":
        """从模型产物加载；缺归一化参数时抛错（不自动计算/保存）。"""
        resolved = resolve_device(device)
        teacher, student, autoencoder = load_models(
            artifacts, resolved, teacher_free=teacher_free
        )
        normalization = load_normalization(artifacts, resolved)
        valid_input_mask = load_valid_input_mask(
            artifacts.model_dir / "mask_config.json", resolved
        )
        return cls(
            teacher=teacher,
            student=student,
            autoencoder=autoencoder,
            normalization=normalization,
            device=resolved,
            teacher_free=teacher_free,
            st_weight=st_weight,
            ae_weight=ae_weight,
            valid_input_mask=valid_input_mask,
        )

    # ── 推理 ──────────────────────────────────────────────────────

    @torch.no_grad()
    def _forward(self, tensors: torch.Tensor):
        """前向三个网络并计算差异图（输入掩膜在 _to_input_tensor 后叠加）。"""
        if self.valid_input_mask is not None:
            tensors = tensors * self.valid_input_mask
        student_out = self.student(tensors)
        autoencoder_out = self.autoencoder(tensors)
        teacher_out = None if self.teacher_free else self.teacher(tensors)
        return scoring.compute_anomaly_maps(
            teacher_out,
            student_out,
            autoencoder_out,
            teacher_free=self.teacher_free,
            teacher_channels=self.teacher_channels,
            ae_channels=self.ae_channels,
            norm=self.normalization,
            st_weight=self.st_weight,
            ae_weight=self.ae_weight,
        )

    @torch.no_grad()
    def maps_tensor(
        self,
        tensors: torch.Tensor,
        sizes: Iterable[tuple[int, int]],
    ) -> torch.Tensor:
        """批量前向 → 组合热力图张量 [N,H,W]（留在模型设备，供 CUDA stream 等异步场景）。

        ``tensors`` 为已预处理(归一化)的 [N,3,256,256] 输入，``sizes`` 为
        每个样本的原始尺寸 (h, w)，热力图按该尺寸回放。
        """
        sizes = list(sizes)
        _raw_st, _raw_ae, _map_st, _map_ae, combined, _raw_combined = self._forward(tensors)
        mask = scoring.feature_valid_mask(self.valid_input_mask, combined)
        if mask is not None:
            combined = combined * mask
        outs = [
            scoring.resize_map(combined[index : index + 1], h, w)
            for index, (h, w) in enumerate(sizes)
        ]
        return torch.cat(outs, dim=0)[:, 0]  # [N,H,W]

    @torch.no_grad()
    def predict(
        self,
        image: np.ndarray,
        *,
        valid_mask: np.ndarray | None = None,
    ) -> ModelPrediction:
        """单张 ROI 图（BGR uint8）推理，返回 ModelPrediction。

        ``valid_mask`` 为 (H,W) 有效区域掩膜（1=有效，与 ROI 阶段 masks 对应），
        loss/score 只在有效区域统计。
        """
        return self.predict_batch([image], valid_masks=None if valid_mask is None else [valid_mask])[0]

    @torch.no_grad()
    def predict_batch(
        self,
        images: Iterable[np.ndarray],
        *,
        valid_masks: Iterable[np.ndarray | None] | None = None,
    ) -> list[ModelPrediction]:
        images = list(images)
        if not images:
            return []
        masks = [None] * len(images) if valid_masks is None else list(valid_masks)
        if len(masks) != len(images):
            raise ValueError("valid_masks 数量必须与 images 一致")

        tensors = torch.stack(
            [_to_input_tensor(image, self.device) for image in images]
        )
        raw_st, raw_ae, map_st, map_ae, combined, raw_combined = self._forward(tensors)

        predictions: list[ModelPrediction] = []
        for index in range(len(images)):
            height, width = images[index].shape[:2]
            valid_mask_t = _mask_to_tensor(masks[index], self.device)
            if valid_mask_t is None:
                valid_mask_t = self.valid_input_mask  # 训练期 mask_config 兜底
            heatmap, loss, score = scoring.finalize(
                raw_combined[index : index + 1],
                combined[index : index + 1],
                valid_mask_256=valid_mask_t,
                out_h=height,
                out_w=width,
            )
            st = None
            if raw_st is not None:
                st_heatmap, st_loss, st_score = scoring.finalize(
                    raw_st[index : index + 1],
                    map_st[index : index + 1],
                    valid_mask_256=valid_mask_t,
                    out_h=height,
                    out_w=width,
                )
                st = (st_loss, st_score, st_heatmap)
            ae_heatmap, ae_loss, ae_score = scoring.finalize(
                raw_ae[index : index + 1],
                map_ae[index : index + 1],
                valid_mask_256=valid_mask_t,
                out_h=height,
                out_w=width,
            )
            predictions.append(
                ModelPrediction(
                    loss=loss,
                    score=score,
                    heatmap=heatmap,
                    st_loss=st[0] if st else None,
                    st_score=st[1] if st else None,
                    st_heatmap=st[2] if st else None,
                    ae_loss=ae_loss,
                    ae_score=ae_score,
                    ae_heatmap=ae_heatmap,
                )
            )
        return predictions


__all__ = ["ModelRunner"]
