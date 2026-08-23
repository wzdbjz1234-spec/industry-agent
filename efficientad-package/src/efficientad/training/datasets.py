"""Dataset helpers used by the EfficientAD training scripts.

These classes are kept deliberately small and match the MVTec directory
contract used by the original EfficientAD implementation.
"""

from __future__ import annotations

from collections.abc import Iterator

from torchvision.datasets import ImageFolder


class ImageFolderWithoutTarget(ImageFolder):
    """ImageFolder that returns only the transformed image."""

    def __getitem__(self, index: int):
        sample, _ = super().__getitem__(index)
        return sample


class ImageFolderWithPath(ImageFolder):
    """ImageFolder that returns ``(image, target, source_path)``."""

    def __getitem__(self, index: int):
        path, _ = self.samples[index]
        sample, target = super().__getitem__(index)
        return sample, target, path


def InfiniteDataloader(loader) -> Iterator:
    """Yield batches forever, restarting the loader after each epoch."""

    iterator = iter(loader)
    while True:
        try:
            yield next(iterator)
        except StopIteration:
            iterator = iter(loader)


__all__ = [
    "ImageFolderWithoutTarget",
    "ImageFolderWithPath",
    "InfiniteDataloader",
]
