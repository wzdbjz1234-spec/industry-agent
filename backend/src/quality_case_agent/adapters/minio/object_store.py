"""MinIO and in-memory implementations of the object storage port."""

from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any

from quality_case_agent.application.ports.object_store import ObjectStore


class InMemoryObjectStore(ObjectStore):
    def __init__(self, bucket: str = "quality-case") -> None:
        self.bucket = bucket
        self._objects: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, payload: bytes, *, content_type: str = "application/octet-stream") -> str:
        self._objects[key] = (bytes(payload), content_type)
        return f"memory://{self.bucket}/{key}"

    def get(self, key: str) -> bytes:
        try:
            return self._objects[key][0]
        except KeyError as exc:
            raise KeyError(f"object not found: {key}") from exc

    def exists(self, key: str) -> bool:
        return key in self._objects

    def presigned_get_url(self, key: str, *, expires_seconds: int = 900) -> str:
        if not self.exists(key):
            raise KeyError(f"object not found: {key}")
        return f"memory://{self.bucket}/{key}?expires={expires_seconds}"

    def sha256(self, key: str) -> str:
        return hashlib.sha256(self.get(key)).hexdigest()


class MinioObjectStore(ObjectStore):
    """Thin provider adapter; SDK details never cross the application port."""

    def __init__(self, client: Any, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    def ensure_bucket(self) -> None:
        from minio.error import S3Error

        try:
            found = self.client.bucket_exists(self.bucket)
        except S3Error:
            found = False
        if not found:
            self.client.make_bucket(self.bucket)

    def put(self, key: str, payload: bytes, *, content_type: str = "application/octet-stream") -> str:
        from io import BytesIO

        self.ensure_bucket()
        self.client.put_object(self.bucket, key, BytesIO(payload), len(payload), content_type=content_type)
        return f"s3://{self.bucket}/{key}"

    def get(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, key)
        try:
            return bytes(response.read())
        finally:
            response.close()
            response.release_conn()

    def exists(self, key: str) -> bool:
        from minio.error import S3Error

        try:
            self.client.stat_object(self.bucket, key)
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                return False
            raise
        return True

    def presigned_get_url(self, key: str, *, expires_seconds: int = 900) -> str:
        return str(self.client.presigned_get_object(
            self.bucket, key, expires=timedelta(seconds=expires_seconds)
        ))
