"""Provider-neutral object storage port.

The application only deals in immutable object bytes and opaque object keys.  MinIO,
S3, and the in-memory test adapter are deliberately hidden behind this seam.
"""

from typing import Protocol


class ObjectStore(Protocol):
    def put(self, key: str, payload: bytes, *, content_type: str = "application/octet-stream") -> str:
        """Store bytes and return the canonical object URI."""

    def get(self, key: str) -> bytes:
        """Read an object by canonical key."""

    def exists(self, key: str) -> bool:
        """Return whether an object exists."""

    def presigned_get_url(self, key: str, *, expires_seconds: int = 900) -> str:
        """Return a short-lived read URL without exposing provider details."""
