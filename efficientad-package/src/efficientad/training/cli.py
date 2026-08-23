"""Console entry point for the complete EfficientAD training workflow."""

from __future__ import annotations

from .efficientad3 import main as _main


def main() -> int:
    return _main()


__all__ = ["main"]
