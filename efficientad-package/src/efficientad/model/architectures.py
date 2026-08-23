"""EfficientAD 网络结构定义。

迁移自 ``EfficientAD-main/common.py``，去掉对 torchvision 的隐式依赖
（仅 torch.nn），从而消除 ``sys.path`` 修改的需要。

注意：实际训练的权重通过 ``torch.save(module)`` 保存为完整的
``nn.Sequential``，加载时不需要引用本模块；本模块用于显式构建网络
（测试、从头训练、导出）。
"""

from __future__ import annotations

from torch import nn


def get_autoencoder(out_channels: int = 384) -> nn.Sequential:
    return nn.Sequential(
        # encoder
        nn.Conv2d(in_channels=3, out_channels=32, kernel_size=4, stride=2, padding=1),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels=32, out_channels=32, kernel_size=4, stride=2, padding=1),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels=32, out_channels=64, kernel_size=4, stride=2, padding=1),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels=64, out_channels=64, kernel_size=4, stride=2, padding=1),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels=64, out_channels=64, kernel_size=4, stride=2, padding=1),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels=64, out_channels=64, kernel_size=8),
        # decoder
        nn.Upsample(size=3, mode="bilinear"),
        nn.Conv2d(in_channels=64, out_channels=64, kernel_size=4, stride=1, padding=2),
        nn.ReLU(inplace=True),
        nn.Dropout(0.2),
        nn.Upsample(size=8, mode="bilinear"),
        nn.Conv2d(in_channels=64, out_channels=64, kernel_size=4, stride=1, padding=2),
        nn.ReLU(inplace=True),
        nn.Dropout(0.2),
        nn.Upsample(size=15, mode="bilinear"),
        nn.Conv2d(in_channels=64, out_channels=64, kernel_size=4, stride=1, padding=2),
        nn.ReLU(inplace=True),
        nn.Dropout(0.2),
        nn.Upsample(size=32, mode="bilinear"),
        nn.Conv2d(in_channels=64, out_channels=64, kernel_size=4, stride=1, padding=2),
        nn.ReLU(inplace=True),
        nn.Dropout(0.2),
        nn.Upsample(size=63, mode="bilinear"),
        nn.Conv2d(in_channels=64, out_channels=64, kernel_size=4, stride=1, padding=2),
        nn.ReLU(inplace=True),
        nn.Dropout(0.2),
        nn.Upsample(size=127, mode="bilinear"),
        nn.Conv2d(in_channels=64, out_channels=64, kernel_size=4, stride=1, padding=2),
        nn.ReLU(inplace=True),
        nn.Dropout(0.2),
        nn.Upsample(size=56, mode="bilinear"),
        nn.Conv2d(in_channels=64, out_channels=64, kernel_size=3, stride=1, padding=1),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels=64, out_channels=out_channels, kernel_size=3, stride=1, padding=1),
    )


def get_pdn_small(out_channels: int = 384, padding: bool = False) -> nn.Sequential:
    pad_mult = 1 if padding else 0
    return nn.Sequential(
        nn.Conv2d(in_channels=3, out_channels=128, kernel_size=4, padding=3 * pad_mult),
        nn.ReLU(inplace=True),
        nn.AvgPool2d(kernel_size=2, stride=2, padding=1 * pad_mult),
        nn.Conv2d(in_channels=128, out_channels=256, kernel_size=4, padding=3 * pad_mult),
        nn.ReLU(inplace=True),
        nn.AvgPool2d(kernel_size=2, stride=2, padding=1 * pad_mult),
        nn.Conv2d(in_channels=256, out_channels=256, kernel_size=3, padding=1 * pad_mult),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels=256, out_channels=out_channels, kernel_size=4),
    )


def get_pdn_medium(out_channels: int = 384, padding: bool = False) -> nn.Sequential:
    pad_mult = 1 if padding else 0
    return nn.Sequential(
        nn.Conv2d(in_channels=3, out_channels=256, kernel_size=4, padding=3 * pad_mult),
        nn.ReLU(inplace=True),
        nn.AvgPool2d(kernel_size=2, stride=2, padding=1 * pad_mult),
        nn.Conv2d(in_channels=256, out_channels=512, kernel_size=4, padding=3 * pad_mult),
        nn.ReLU(inplace=True),
        nn.AvgPool2d(kernel_size=2, stride=2, padding=1 * pad_mult),
        nn.Conv2d(in_channels=512, out_channels=512, kernel_size=1),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels=512, out_channels=512, kernel_size=3, padding=1 * pad_mult),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels=512, out_channels=out_channels, kernel_size=4),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels=out_channels, out_channels=out_channels, kernel_size=1),
    )


def get_pdn_tiny(out_channels: int = 384, padding: bool = False) -> nn.Sequential:
    pad_mult = 1 if padding else 0
    return nn.Sequential(
        nn.Conv2d(in_channels=3, out_channels=64, kernel_size=4, padding=3 * pad_mult),
        nn.ReLU(inplace=True),
        nn.AvgPool2d(kernel_size=2, stride=2, padding=1 * pad_mult),
        nn.Conv2d(in_channels=64, out_channels=128, kernel_size=4, padding=3 * pad_mult),
        nn.ReLU(inplace=True),
        nn.AvgPool2d(kernel_size=2, stride=2, padding=1 * pad_mult),
        nn.Conv2d(in_channels=128, out_channels=128, kernel_size=3, padding=1 * pad_mult),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels=128, out_channels=out_channels, kernel_size=4),
    )


def get_autoencoder_tiny(out_channels: int = 384) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(in_channels=3, out_channels=16, kernel_size=4, stride=2, padding=1),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels=16, out_channels=16, kernel_size=4, stride=2, padding=1),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels=16, out_channels=32, kernel_size=4, stride=2, padding=1),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels=32, out_channels=32, kernel_size=4, stride=2, padding=1),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels=32, out_channels=32, kernel_size=4, stride=2, padding=1),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels=32, out_channels=32, kernel_size=8),
        nn.Upsample(size=3, mode="bilinear"),
        nn.Conv2d(in_channels=32, out_channels=32, kernel_size=4, stride=1, padding=2),
        nn.ReLU(inplace=True),
        nn.Dropout(0.2),
        nn.Upsample(size=8, mode="bilinear"),
        nn.Conv2d(in_channels=32, out_channels=32, kernel_size=4, stride=1, padding=2),
        nn.ReLU(inplace=True),
        nn.Dropout(0.2),
        nn.Upsample(size=15, mode="bilinear"),
        nn.Conv2d(in_channels=32, out_channels=32, kernel_size=4, stride=1, padding=2),
        nn.ReLU(inplace=True),
        nn.Dropout(0.2),
        nn.Upsample(size=32, mode="bilinear"),
        nn.Conv2d(in_channels=32, out_channels=32, kernel_size=4, stride=1, padding=2),
        nn.ReLU(inplace=True),
        nn.Dropout(0.2),
        nn.Upsample(size=63, mode="bilinear"),
        nn.Conv2d(in_channels=32, out_channels=32, kernel_size=4, stride=1, padding=2),
        nn.ReLU(inplace=True),
        nn.Dropout(0.2),
        nn.Upsample(size=127, mode="bilinear"),
        nn.Conv2d(in_channels=32, out_channels=32, kernel_size=4, stride=1, padding=2),
        nn.ReLU(inplace=True),
        nn.Dropout(0.2),
        nn.Upsample(size=56, mode="bilinear"),
        nn.Conv2d(in_channels=32, out_channels=32, kernel_size=3, stride=1, padding=1),
        nn.ReLU(inplace=True),
        nn.Conv2d(in_channels=32, out_channels=out_channels, kernel_size=3, stride=1, padding=1),
    )


__all__ = [
    "get_autoencoder",
    "get_autoencoder_tiny",
    "get_pdn_medium",
    "get_pdn_small",
    "get_pdn_tiny",
]
