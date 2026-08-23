"""训练包：归一化参数显式校准（无副作用约束的配套命令）。

推理路径不得隐式计算/保存归一化参数（REFACTOR_PLAN.md 第 5.2 节）；
本模块提供唯一的显式入口：

    python -m efficientad.training.calibration --model 30 --product 111 --train-dir mydataset/111/train

计算 teacher_mean/teacher_std 与 map 分位数(q_*)，写入模型目录的
norm_params.json。需要完整 norm_params 的模型加载（ModelRunner.load）
在缺失时直接报错并提示运行本命令。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from tqdm import tqdm

from efficientad.model.artifacts import ModelArtifacts
from efficientad.model.loader import load_models, load_valid_input_mask, resolve_device
from efficientad.model.normalization import NormalizationParams
from efficientad.model.scoring import feature_valid_mask

DEFAULT_IMAGE_SIZE = 256
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

_DEFAULT_TRANSFORM = transforms.Compose(
    [
        transforms.Resize((DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ]
)


def discover_images(path: str | Path) -> list[Path]:
    source = Path(path).expanduser().resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"训练目录不存在: {source}")
    return sorted(
        item for item in source.rglob("*")
        if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS
    )


class _ImageDataset(Dataset):
    def __init__(self, paths: list[Path]) -> None:
        self.paths = paths

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, index: int) -> torch.Tensor:
        with Image.open(self.paths[index]) as image:
            return _DEFAULT_TRANSFORM(image.convert("RGB"))


@torch.no_grad()
def compute_normalization(
    teacher: torch.nn.Module,
    student: torch.nn.Module,
    autoencoder: torch.nn.Module,
    train_dir: Path,
    device: torch.device,
    valid_input_mask: torch.Tensor | None = None,
) -> NormalizationParams:
    """在训练集上计算归一化参数（与旧 predictor._compute_normalization 一致）。"""
    paths = discover_images(train_dir)
    if not paths:
        raise ValueError(f"训练目录下没有图片: {train_dir}")
    loader = DataLoader(_ImageDataset(paths), batch_size=1, shuffle=False, num_workers=0)

    means = []
    for images in tqdm(loader, desc="Teacher mean"):
        images = images.to(device)
        if valid_input_mask is not None:
            images = images * valid_input_mask
        output = teacher(images)
        mask = feature_valid_mask(valid_input_mask, output)
        if mask is None:
            mean = torch.mean(output, dim=(0, 2, 3))
        else:
            count = mask.sum() * output.shape[0]
            mean = (output * mask).sum(dim=(0, 2, 3)) / count
        means.append(mean.cpu())
    teacher_mean = torch.mean(torch.stack(means), dim=0).reshape(1, -1, 1, 1)
    teacher_mean = teacher_mean.to(device)

    variances = []
    for images in tqdm(loader, desc="Teacher std"):
        images = images.to(device)
        if valid_input_mask is not None:
            images = images * valid_input_mask
        output = teacher(images)
        distance = (output - teacher_mean) ** 2
        mask = feature_valid_mask(valid_input_mask, distance)
        if mask is None:
            variance = torch.mean(distance, dim=(0, 2, 3))
        else:
            count = mask.sum() * distance.shape[0]
            variance = (distance * mask).sum(dim=(0, 2, 3)) / count
        variances.append(variance.cpu())
    teacher_std = torch.sqrt(torch.mean(torch.stack(variances), dim=0))
    teacher_std = teacher_std.reshape(1, -1, 1, 1).to(device)

    teacher_channels = teacher[-1].out_channels if isinstance(teacher, torch.nn.Sequential) else 384
    ae_channels = autoencoder[-1].out_channels if isinstance(autoencoder, torch.nn.Sequential) else 384

    maps_st, maps_ae = [], []
    for images in tqdm(loader, desc="Map quantiles"):
        images = images.to(device)
        if valid_input_mask is not None:
            images = images * valid_input_mask
        teacher_output = (teacher(images) - teacher_mean) / teacher_std
        student_output = student(images)
        autoencoder_output = autoencoder(images)
        map_st = torch.mean(
            (teacher_output - student_output[:, :teacher_channels]) ** 2, dim=1, keepdim=True
        )
        map_ae = torch.mean(
            (autoencoder_output - student_output[:, teacher_channels : teacher_channels + ae_channels]) ** 2,
            dim=1,
            keepdim=True,
        )
        mask = feature_valid_mask(valid_input_mask, map_st)
        if mask is None:
            maps_st.append(map_st.flatten().cpu())
            maps_ae.append(map_ae.flatten().cpu())
        else:
            maps_st.append(map_st.masked_select(mask).cpu())
            maps_ae.append(map_ae.masked_select(mask).cpu())

    all_st = torch.cat(maps_st)
    all_ae = torch.cat(maps_ae)
    return NormalizationParams(
        teacher_mean=teacher_mean,
        teacher_std=teacher_std,
        q_st_start=torch.quantile(all_st, 0.9).to(device),
        q_st_end=torch.quantile(all_st, 0.995).to(device),
        q_ae_start=torch.quantile(all_ae, 0.9).to(device),
        q_ae_end=torch.quantile(all_ae, 0.995).to(device),
    )


def calibrate(
    model: str | Path,
    product: str,
    train_dir: str | Path,
    *,
    source_dir: str | Path,
    device: str = "auto",
) -> Path:
    artifacts = ModelArtifacts.from_output(model, product=product, source_dir=source_dir)
    resolved = resolve_device(device)
    teacher, student, autoencoder = load_models(artifacts, resolved, teacher_free=False)
    valid_input_mask = load_valid_input_mask(artifacts.model_dir / "mask_config.json", resolved)
    params = compute_normalization(
        teacher, student, autoencoder, Path(train_dir), resolved, valid_input_mask
    )
    params.save(artifacts.norm_params)
    print(f"[calibration] 已保存归一化参数: {artifacts.norm_params}")
    return artifacts.norm_params


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="calibration", description=__doc__)
    parser.add_argument("--model", required=True, help="output 编号或模型目录")
    parser.add_argument("--product", default="my_product")
    parser.add_argument("--source-dir", default=str(Path.cwd()))
    parser.add_argument("--train-dir", required=True, help="训练图片目录(用于计算归一化参数)")
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    calibrate(
        args.model, args.product, args.train_dir,
        source_dir=args.source_dir, device=args.device,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
