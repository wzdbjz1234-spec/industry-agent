"""Offline embedding provider for tests, demos and local development."""

from __future__ import annotations

import hashlib
import math


class DeterministicEmbeddingProvider:
    """Create a stable low-dimensional vector without external model calls."""

    def __init__(self, dimensions: int = 32) -> None:
        if dimensions < 4:
            raise ValueError("embedding dimensions must be at least 4")
        self.dimensions = dimensions

    def embed(self, text: str) -> tuple[float, ...]:
        if not text.strip():
            raise ValueError("cannot embed empty text")
        values = [0.0] * self.dimensions
        normalized = text.lower().encode("utf-8")
        for index in range(max(1, len(normalized) - 2)):
            token = normalized[index : index + 3]
            digest = hashlib.sha256(token).digest()
            bucket = int.from_bytes(digest[:2], "big") % self.dimensions
            values[bucket] += 1.0 if digest[2] % 2 else -1.0
        norm = math.sqrt(sum(value * value for value in values))
        return tuple(value / norm for value in values) if norm else tuple(values)
