"""Compatibility surface for the original ``EfficientAD-main/common.py``.

Network constructors now live in :mod:`efficientad.model.architectures` and
the dataset helpers live in :mod:`efficientad.training.datasets`.  Re-exporting
them here keeps the migrated upstream scripts readable and preserves their
original import names inside the package.
"""

from efficientad.model.architectures import (
    get_autoencoder,
    get_autoencoder_tiny,
    get_pdn_medium,
    get_pdn_small,
    get_pdn_tiny,
)

from .datasets import InfiniteDataloader, ImageFolderWithPath, ImageFolderWithoutTarget

__all__ = [
    "get_autoencoder",
    "get_autoencoder_tiny",
    "get_pdn_medium",
    "get_pdn_small",
    "get_pdn_tiny",
    "ImageFolderWithoutTarget",
    "ImageFolderWithPath",
    "InfiniteDataloader",
]
