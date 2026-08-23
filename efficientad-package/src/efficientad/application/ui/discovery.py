"""UI 辅助：模型与 ORB 模板发现（纯函数，可独立测试）。

模型布局约定（与 ModelArtifacts 一致）：
``<source_dir>/output/<model>/trainings/mvtec_ad/<product>/``
可用条件：student/autoencoder final 权重 + norm_params.json 齐全。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

REQUIRED_FILES = ("student_final.pth", "autoencoder_final.pth", "norm_params.json")


@dataclass(frozen=True)
class ModelInfo:
    model: str          # output 编号或目录名，如 "30"
    product: str        # 产品名，如 "111"
    model_dir: Path     # 模型产物目录（含 *_final.pth 与 norm_params.json）
    threshold: float | None = None

    @property
    def label(self) -> str:
        return f"{self.model} / {self.product}"


@dataclass(frozen=True)
class WeightInfo:
    """可直接用于 teacher-free 推理的模型产物目录。"""

    model_dir: Path
    threshold: float | None = None

    @property
    def label(self) -> str:
        return str(self.model_dir)


def inspect_weight_dir(path: str | Path) -> dict[str, bool]:
    """返回模型目录三类关键文件是否齐全，供 UI 状态提示使用。"""

    directory = Path(path).expanduser()
    return {
        "student": (directory / "student_final.pth").is_file(),
        "autoencoder": (directory / "autoencoder_final.pth").is_file(),
        "normalization": (directory / "norm_params.json").is_file(),
    }


def load_threshold(model_dir: str | Path) -> float | None:
    """读取 threshold.json 中的决策阈值；不存在或非法返回 None。"""
    path = Path(model_dir) / "threshold.json"
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle).get("threshold")
        return None if value is None else float(value)
    except (ValueError, json.JSONDecodeError):
        return None


def _model_sort_key(path: Path) -> tuple:
    """模型目录自然排序：数字编号按数值，其余按字母。"""
    name = path.name
    if name.isdigit():
        return (0, int(name), "")
    return (1, name.lower(), "")


def discover_models(source_dir: str | Path) -> list[ModelInfo]:
    """扫描 ``<source_dir>/output/*/trainings/mvtec_ad/*/`` 下的可用模型。"""
    root = Path(source_dir).expanduser().resolve()
    output_dir = root / "output"
    if not output_dir.is_dir():
        return []

    models: list[ModelInfo] = []
    for model_dir in sorted(output_dir.iterdir(), key=_model_sort_key):
        trainings = model_dir / "trainings" / "mvtec_ad"
        if not trainings.is_dir():
            continue
        for product_dir in sorted(trainings.iterdir()):
            if not product_dir.is_dir():
                continue
            if all((product_dir / name).is_file() for name in REQUIRED_FILES):
                models.append(
                    ModelInfo(
                        model=model_dir.name,
                        product=product_dir.name,
                        model_dir=product_dir,
                        threshold=load_threshold(product_dir),
                    )
                )
    return models


def discover_weight_dirs(source_dir: str | Path) -> list[WeightInfo]:
    """递归发现 output 下的完整权重目录，不依赖 model/product 命名。"""

    root = Path(source_dir).expanduser().resolve()
    output_dir = root if root.name.lower() == "output" else root / "output"
    if not output_dir.is_dir():
        return []

    found: dict[Path, WeightInfo] = {}
    for student_path in output_dir.rglob("student_final.pth"):
        model_dir = student_path.parent
        if all((model_dir / name).is_file() for name in REQUIRED_FILES):
            resolved = model_dir.resolve()
            found[resolved] = WeightInfo(resolved, load_threshold(resolved))
    return [found[path] for path in sorted(found)]


def resolve_weight_dir(path: str | Path) -> Path:
    """把用户选中的目录/权重文件解析成完整模型产物目录。"""

    candidate = Path(path).expanduser().resolve()
    if candidate.is_file():
        candidate = candidate.parent
    if all((candidate / name).is_file() for name in REQUIRED_FILES):
        return candidate
    if candidate.is_dir():
        matches = sorted(
            parent
            for parent in {item.parent for item in candidate.rglob("student_final.pth")}
            if all((parent / name).is_file() for name in REQUIRED_FILES)
        )
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError("所选目录包含多个模型，请直接选择某个模型产物目录")
    raise FileNotFoundError(
        "模型目录必须同时包含 student_final.pth、autoencoder_final.pth 和 norm_params.json: "
        f"{candidate}"
    )


def discover_templates(templates_dir: str | Path | None = None) -> list[str]:
    """列出 ORB 模板名（模板目录下含 template.png + roi.json 的子目录）。"""
    base = Path(templates_dir) if templates_dir else _default_templates_dir()
    if not base.is_dir():
        return []
    return sorted(
        entry.name
        for entry in base.iterdir()
        if entry.is_dir()
        and (entry / "template.png").is_file()
        and (entry / "roi.json").is_file()
    )


def _default_templates_dir() -> Path:
    """默认模板目录：当前目录 → 独立包根 → 仓库根（与 orb.py 一致）。"""
    this = Path(__file__).resolve()
    for candidate in (
        Path.cwd() / "templates",
        this.parents[4] / "templates",  # 独立包根（src/efficientad/application/ui/...）
        this.parents[5] / "templates",  # 仓库根（开发布局）
    ):
        if candidate.is_dir():
            return candidate
    return Path.cwd() / "templates"


__all__ = [
    "ModelInfo",
    "WeightInfo",
    "discover_models",
    "discover_templates",
    "discover_weight_dirs",
    "inspect_weight_dir",
    "load_threshold",
    "resolve_weight_dir",
]
