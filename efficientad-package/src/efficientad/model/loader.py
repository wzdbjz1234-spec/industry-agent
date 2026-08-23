"""模型加载与设备选择。

无副作用约束（REFACTOR_PLAN.md 第 5.2 节）：
- 缺少 norm_params.json 时直接抛错，并提示执行显式校准命令；
- 加载过程不写任何缓存文件。
"""

from __future__ import annotations

import json
from pathlib import Path

import torch
import torch.nn.functional as F
from torch import nn

from .artifacts import ModelArtifacts
from .normalization import NormalizationParams

DEFAULT_IMAGE_SIZE = 256


def resolve_device(device: str | torch.device) -> torch.device:
    if isinstance(device, torch.device):
        return device
    if device == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    resolved = torch.device(device)
    if resolved.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    return resolved


def load_module(path: Path, device: torch.device) -> nn.Module:
    """加载 torch.save(module) 保存的完整模型并置为 eval 模式。"""
    module = torch.load(path, map_location=device, weights_only=False)
    module.to(device)
    module.eval()
    return module


def load_models(
    artifacts: ModelArtifacts,
    device: torch.device,
    *,
    teacher_free: bool = True,
) -> tuple[nn.Module | None, nn.Module, nn.Module]:
    """加载 teacher(student/autoencoder)。

    返回 ``(teacher, student, autoencoder)``；teacher-free 模式 teacher 为 None。
    """
    required = [artifacts.student, artifacts.autoencoder]
    if not teacher_free:
        required.append(artifacts.teacher)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing model weights:\n  " + "\n  ".join(missing))

    teacher = None if teacher_free else load_module(artifacts.teacher, device)
    student = load_module(artifacts.student, device)
    autoencoder = load_module(artifacts.autoencoder, device)
    return teacher, student, autoencoder


def load_normalization(artifacts: ModelArtifacts, device: torch.device) -> NormalizationParams:
    """加载归一化参数；缺失时抛错，不隐式计算/保存。"""
    if not artifacts.norm_params.is_file():
        raise FileNotFoundError(
            f"Normalization cache not found: {artifacts.norm_params}.\n"
            "推理路径不会自动计算。请先运行显式校准命令: "
            "python -m efficientad.training.calibration --model <id>"
        )
    normalization = NormalizationParams.load(artifacts.norm_params, device)
    if normalization is None:
        raise ValueError(
            f"归一化参数格式不完整(需要 teacher_mean/teacher_std/q_*): "
            f"{artifacts.norm_params}"
        )
    return normalization


def load_valid_input_mask(path: Path, device: torch.device) -> torch.Tensor | None:
    """从训练期 mask_config.json 读取输入有效掩膜(256x256)，不存在则返回 None。"""
    if not Path(path).is_file():
        return None
    with Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    _, _, roi_width, roi_height = map(int, data["roi"])
    raw_masks = data.get("masks")
    if raw_masks is None:
        raw_mask = data.get("mask")
        raw_masks = [] if raw_mask is None else [raw_mask]
    if not raw_masks:
        return None

    valid = torch.ones((1, 1, roi_height, roi_width), dtype=torch.float32)
    for raw_mask in raw_masks:
        x, y, width, height = map(int, raw_mask)
        if (
            width <= 0 or height <= 0 or x < 0 or y < 0
            or x + width > roi_width or y + height > roi_height
        ):
            raise ValueError(
                f"Mask ({x},{y},{width},{height}) is outside "
                f"ROI {roi_width}x{roi_height}: {path}"
            )
        valid[:, :, y : y + height, x : x + width] = 0
    valid = F.interpolate(valid, size=(DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE), mode="nearest")
    if not torch.any(valid):
        raise ValueError(f"Mask excludes the entire ROI: {path}")
    return valid.to(device)


__all__ = [
    "load_models",
    "load_normalization",
    "load_valid_input_mask",
    "resolve_device",
]
