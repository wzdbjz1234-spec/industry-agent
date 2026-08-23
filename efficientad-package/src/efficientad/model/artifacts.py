"""模型产物（权重、归一化参数）路径定位。

迁移自 ``efficientad_tools/artifacts.py``，语义不变。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path


def default_project_root() -> Path:
    """智能定位项目根（包含 ``output/`` 的目录）。

    候选顺序：当前工作目录 → 仓库根(开发布局 src/efficientad/...) →
    独立包根(efficientad-package/)。均不满足时回退到当前工作目录。
    """
    this = Path(__file__).resolve()
    candidates = [
        Path.cwd(),
        this.parents[4],  # 开发布局: 仓库根
        this.parents[3],  # 独立包布局: efficientad-package/
    ]
    for candidate in candidates:
        if (candidate / "output").is_dir():
            return candidate
    return Path.cwd()


PROJECT_ROOT = default_project_root()


@dataclass(frozen=True)
class ModelArtifacts:
    """从一个训练输出目录恢复模型所需的全部文件路径。"""

    model_dir: Path
    teacher: Path
    student: Path
    autoencoder: Path
    norm_params: Path
    source_dir: Path

    @classmethod
    def from_output(
        cls,
        model: str | Path,
        *,
        dataset: str = "mvtec_ad",
        product: str = "my_product",
        source_dir: str | Path = PROJECT_ROOT,
    ) -> "ModelArtifacts":
        source = Path(source_dir).expanduser().resolve()
        requested = Path(model).expanduser()

        if requested.is_dir():
            model_dir = requested.resolve()
            if not (model_dir / "teacher_final.pth").is_file():
                nested = model_dir / "trainings" / dataset / product
                if nested.is_dir():
                    model_dir = nested
        else:
            model_dir = source / "output" / str(model) / "trainings" / dataset / product

        return cls.from_directory(model_dir, source_dir=source)

    @classmethod
    def from_directory(
        cls,
        model_dir: str | Path,
        *,
        source_dir: str | Path = PROJECT_ROOT,
    ) -> "ModelArtifacts":
        directory = Path(model_dir).expanduser().resolve()
        return cls(
            model_dir=directory,
            teacher=directory / "teacher_final.pth",
            student=directory / "student_final.pth",
            autoencoder=directory / "autoencoder_final.pth",
            norm_params=directory / "norm_params.json",
            source_dir=Path(source_dir).expanduser().resolve(),
        )

    def with_overrides(
        self,
        *,
        teacher: str | Path | None = None,
        student: str | Path | None = None,
        autoencoder: str | Path | None = None,
        norm_params: str | Path | None = None,
    ) -> "ModelArtifacts":
        def resolved(value: str | Path | None, current: Path) -> Path:
            return Path(value).expanduser().resolve() if value else current

        return replace(
            self,
            teacher=resolved(teacher, self.teacher),
            student=resolved(student, self.student),
            autoencoder=resolved(autoencoder, self.autoencoder),
            norm_params=resolved(norm_params, self.norm_params),
        )

    def validate(self, *, require_norm: bool = True) -> "ModelArtifacts":
        required = {
            "student weights": self.student,
            "autoencoder weights": self.autoencoder,
        }
        if require_norm:
            required["normalization parameters"] = self.norm_params
        missing = [
            f"{name}: {path}" for name, path in required.items() if not path.exists()
        ]
        if missing:
            raise FileNotFoundError(
                "Missing model artifacts:\n  " + "\n  ".join(missing)
            )
        return self

    def as_dict(self) -> dict[str, str]:
        return {
            "model_dir": str(self.model_dir),
            "teacher": str(self.teacher),
            "student": str(self.student),
            "autoencoder": str(self.autoencoder),
            "norm_params": str(self.norm_params),
            "source_dir": str(self.source_dir),
        }


__all__ = ["ModelArtifacts"]
