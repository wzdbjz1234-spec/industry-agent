"""评分与热力图计算的纯函数。

无模型加载、无文件 IO，输入输出均为 torch 张量 / numpy 数组，
便于独立单元测试。指标定义见 REFACTOR_PLAN.md 阶段 0 执行记录：

    loss    = 原始异常差异图（归一化前）在有效区域内的平均值
    score   = 归一化异常图在有效区域内的最大值
    heatmap = 归一化异常图，float32，(H, W)
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F

PAD = 4  # 与 dual_detector / predictor 一致的回放前 padding


def mean_squared_map(target: torch.Tensor, mimic: torch.Tensor) -> torch.Tensor:
    """通道维均值平方差异图 [N,1,Hf,Wf]（原始异常差异图）。"""
    return torch.mean((target - mimic) ** 2, dim=1, keepdim=True)


def normalize_map(value: torch.Tensor, start: torch.Tensor, end: torch.Tensor) -> torch.Tensor:
    """0.1 * (v - start) / (end - start)，与现有流水线完全一致。"""
    denominator = end - start
    if torch.isclose(denominator, torch.zeros_like(denominator)):
        return torch.zeros_like(value)
    return 0.1 * (value - start) / denominator


def compute_anomaly_maps(
    teacher_out: torch.Tensor | None,
    student_out: torch.Tensor,
    autoencoder_out: torch.Tensor,
    *,
    teacher_free: bool,
    teacher_channels: int,
    ae_channels: int,
    norm,
    st_weight: float = 0.0,
    ae_weight: float = 1.0,
) -> tuple[torch.Tensor | None, torch.Tensor, torch.Tensor | None, torch.Tensor, torch.Tensor, torch.Tensor]:
    """计算原始差异图与归一化差异图。

    返回 ``(raw_st, raw_ae, map_st, map_ae, combined, raw_combined)``：
    - raw_* : 归一化前的原始差异图 [N,1,Hf,Wf]；
    - map_* : 0.1 分位数归一化后的图；
    - combined : ``st_weight*map_st + ae_weight*map_ae``（teacher-free 时 map_st 为 None）；
    - raw_combined : 与 combined 对应的归一化前组合图。
    """
    if teacher_free:
        raw_st = map_st = None
        raw_ae = mean_squared_map(autoencoder_out, student_out[:, -ae_channels:])
    else:
        if teacher_out is None:
            raise ValueError("teacher_free=False 时必须提供 teacher 输出")
        raw_st = mean_squared_map(teacher_out, student_out[:, :teacher_channels])
        raw_ae = mean_squared_map(
            autoencoder_out, student_out[:, teacher_channels : teacher_channels + ae_channels]
        )
        map_st = normalize_map(raw_st, norm.q_st_start, norm.q_st_end)

    map_ae = normalize_map(raw_ae, norm.q_ae_start, norm.q_ae_end)
    if teacher_free:
        combined = ae_weight * map_ae
        raw_combined = ae_weight * raw_ae
    else:
        combined = st_weight * map_st + ae_weight * map_ae
        raw_combined = st_weight * raw_st + ae_weight * raw_ae
    return raw_st, raw_ae, map_st, map_ae, combined, raw_combined


def feature_valid_mask(
    valid_mask_256: torch.Tensor | None, reference: torch.Tensor
) -> torch.Tensor | None:
    """把输入分辨率(256x256)的有效掩膜缩放到特征图分辨率。"""
    if valid_mask_256 is None:
        return None
    return (
        F.interpolate(valid_mask_256, size=reference.shape[-2:], mode="nearest").bool()
    )


def resize_map(value: torch.Tensor, height: int, width: int) -> torch.Tensor:
    """pad(PAD) + 双线性回放到 (height, width)，保持与现有流水线一致。"""
    padded = F.pad(value, (PAD, PAD, PAD, PAD))
    return F.interpolate(padded, size=(height, width), mode="bilinear", align_corners=False)


def finalize(
    raw_combined: torch.Tensor,
    combined: torch.Tensor,
    *,
    valid_mask_256: torch.Tensor | None,
    out_h: int,
    out_w: int,
) -> tuple[np.ndarray, float, float]:
    """回放热力图并计算 loss/score（有效区域内统计）。

    返回 ``(heatmap_np, loss, score)``：
    - heatmap : 归一化 combined 回放到 (out_h, out_w)，掩膜像素置 0，float32；
    - score   : 有效区域内最大值；
    - loss    : 原始差异图回放到 (out_h, out_w) 后有效区域内的平均值。
    """
    mask_ = feature_valid_mask(valid_mask_256, combined)
    combined_valid = combined
    raw_valid = raw_combined
    if mask_ is not None:
        combined_valid = combined * mask_
        raw_valid = raw_combined * mask_

    heatmap = resize_map(combined_valid, out_h, out_w)
    raw_resized = resize_map(raw_valid, out_h, out_w)

    output_mask = None
    if valid_mask_256 is not None:
        output_mask = (
            F.interpolate(valid_mask_256, size=(out_h, out_w), mode="nearest")
            .float()
        )
        heatmap = heatmap * output_mask
        raw_resized = raw_resized * output_mask

    heatmap_np = heatmap[0, 0].detach().cpu().numpy()

    # score: 有效区域最大值（掩膜像素置 0 后天然排除）
    score = float(heatmap_np.max())
    # loss: 有效区域平均值
    if output_mask is not None:
        valid = output_mask[0, 0].detach().cpu().numpy() > 0
        loss = float(raw_resized[0, 0].detach().cpu().numpy()[valid].mean())
    else:
        loss = float(raw_resized[0, 0].detach().cpu().numpy().mean())
    return heatmap_np, loss, score


__all__ = [
    "compute_anomaly_maps",
    "feature_valid_mask",
    "finalize",
    "mean_squared_map",
    "normalize_map",
    "resize_map",
]
