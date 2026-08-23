"""归一化参数（NormalizationParams）。

迁移自 ``efficientad_tools/predictor.py``。``load`` 只读不写；
计算并保存归一化参数属于显式校准流程（``efficientad.training.calibration``），
推理路径不得隐式落盘。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch


@dataclass(frozen=True)
class NormalizationParams:
    teacher_mean: torch.Tensor
    teacher_std: torch.Tensor
    q_st_start: torch.Tensor
    q_st_end: torch.Tensor
    q_ae_start: torch.Tensor
    q_ae_end: torch.Tensor

    @classmethod
    def load(cls, path: str | Path, device: torch.device) -> "NormalizationParams | None":
        with Path(path).open(encoding="utf-8") as handle:
            data = json.load(handle)

        required = (
            "teacher_mean", "teacher_std", "q_st_start", "q_st_end",
            "q_ae_start", "q_ae_end",
        )
        if any(key not in data for key in required):
            return None

        def tensor(value: Any) -> torch.Tensor:
            return torch.as_tensor(value, dtype=torch.float32, device=device)

        return cls(
            teacher_mean=tensor(data["teacher_mean"]).reshape(1, -1, 1, 1),
            teacher_std=tensor(data["teacher_std"]).reshape(1, -1, 1, 1),
            q_st_start=tensor(data["q_st_start"]),
            q_st_end=tensor(data["q_st_end"]),
            q_ae_start=tensor(data["q_ae_start"]),
            q_ae_end=tensor(data["q_ae_end"]),
        )

    def save(self, path: str | Path) -> None:
        """显式保存（仅供校准命令调用，推理路径不得调用）。"""
        payload = {
            "teacher_mean": self.teacher_mean.detach().cpu().flatten().tolist(),
            "teacher_std": self.teacher_std.detach().cpu().flatten().tolist(),
            "q_st_start": float(self.q_st_start.detach().cpu()),
            "q_st_end": float(self.q_st_end.detach().cpu()),
            "q_ae_start": float(self.q_ae_start.detach().cpu()),
            "q_ae_end": float(self.q_ae_end.detach().cpu()),
        }
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)


__all__ = ["NormalizationParams"]
