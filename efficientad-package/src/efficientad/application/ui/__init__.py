"""UI 包：EfficientAD 图像检测图形界面（tkinter）。"""

from .app import EfficientADUI, main
from .discovery import (
    ModelInfo,
    WeightInfo,
    discover_models,
    discover_templates,
    discover_weight_dirs,
    inspect_weight_dir,
    load_threshold,
    resolve_weight_dir,
)

__all__ = [
    "EfficientADUI",
    "ModelInfo",
    "WeightInfo",
    "discover_models",
    "discover_templates",
    "discover_weight_dirs",
    "inspect_weight_dir",
    "load_threshold",
    "resolve_weight_dir",
    "main",
]
