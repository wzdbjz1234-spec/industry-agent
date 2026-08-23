"""EfficientAD training package.

The package contains the complete upstream training workflow, including
MVTec-compatible datasets, teacher/student/autoencoder optimization,
normalization calibration, and auxiliary pretraining/distillation tools.
"""

from .calibration import calibrate, compute_normalization
from .datasets import InfiniteDataloader, ImageFolderWithPath, ImageFolderWithoutTarget

__all__ = ["calibrate", "compute_normalization"]
__all__ += [
    "train",
    "ImageFolderWithoutTarget",
    "ImageFolderWithPath",
    "InfiniteDataloader",
]


def train(argv=None) -> int:
    """Run the complete EfficientAD trainer with CLI-style arguments."""

    from .efficientad3 import main

    return main(argv)
