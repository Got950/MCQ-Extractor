"""Storage backends for uploaded PDFs.

Two backends, one interface:

- ``LocalStorage``  writes/reads from ``settings.upload_dir`` (dev default).
- ``S3Storage``     uses boto3; selected when ``S3_BUCKET`` is set.

The Job table only stores an opaque ``pdf_key`` string. The active backend
knows how to turn that key into a temporary local file for downstream
processing (PyMuPDF + Gemini both need a real path or bytes).
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from config import settings

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Common interface for local + S3 storage."""

    @abstractmethod
    def write_stream(self, key: str, stream_iter) -> int:
        """Write an iterable of byte chunks under ``key``. Returns bytes written."""

    @abstractmethod
    def open_local(self, key: str) -> "AbstractContextManager[str]":
        """Yield a local filesystem path to read the object from."""

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def list_old_keys(self, older_than_seconds: int) -> list[str]:
        """Keys whose mtime/created_at is older than the cutoff."""


class LocalStorage(StorageBackend):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Prevent path traversal by stripping separators.
        safe = key.replace("/", "_").replace("\\", "_")
        return self.root / safe

    def write_stream(self, key: str, stream_iter) -> int:
        target = self._path(key)
        total = 0
        with target.open("wb") as fh:
            for chunk in stream_iter:
                if not chunk:
                    continue
                fh.write(chunk)
                total += len(chunk)
        return total

    @contextmanager
    def open_local(self, key: str) -> Iterator[str]:
        yield str(self._path(key))

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def list_old_keys(self, older_than_seconds: int) -> list[str]:
        cutoff = time.time() - older_than_seconds
        old: list[str] = []
        for path in self.root.iterdir():
            if not path.is_file():
                continue
            try:
                if path.stat().st_mtime < cutoff:
                    old.append(path.name)
            except OSError:
                continue
        return old


class S3Storage(StorageBackend):
    def __init__(self, bucket: str, region: str | None, endpoint: str | None) -> None:
        import boto3  # local import keeps boto3 optional at runtime

        self.bucket = bucket
        client_kwargs: dict = {}
        if region:
            client_kwargs["region_name"] = region
        if endpoint:
            client_kwargs["endpoint_url"] = endpoint
        self._client = boto3.client("s3", **client_kwargs)

    def write_stream(self, key: str, stream_iter) -> int:
        # Buffer to tempfile to support resumable multipart by boto3.
        total = 0
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            for chunk in stream_iter:
                if not chunk:
                    continue
                tmp.write(chunk)
                total += len(chunk)
        try:
            self._client.upload_file(tmp_path, self.bucket, key)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        return total

    @contextmanager
    def open_local(self, key: str) -> Iterator[str]:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            local_path = tmp.name
        try:
            self._client.download_file(self.bucket, key, local_path)
            yield local_path
        finally:
            try:
                os.unlink(local_path)
            except OSError:
                pass

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.bucket, Key=key)
        except Exception:
            logger.exception("S3 delete failed for %s", key)

    def list_old_keys(self, older_than_seconds: int) -> list[str]:
        import datetime as _dt

        cutoff = _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(
            seconds=older_than_seconds
        )
        old: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket):
            for obj in page.get("Contents", []) or []:
                if obj.get("LastModified") and obj["LastModified"] < cutoff:
                    old.append(obj["Key"])
        return old


_backend: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _backend
    if _backend is not None:
        return _backend
    if settings.use_s3:
        _backend = S3Storage(
            bucket=settings.s3_bucket,  # type: ignore[arg-type]
            region=settings.s3_region,
            endpoint=settings.s3_endpoint,
        )
        logger.info("Storage backend: S3 bucket=%s", settings.s3_bucket)
    else:
        _backend = LocalStorage(settings.upload_dir)
        logger.info("Storage backend: local dir=%s", settings.upload_dir)
    return _backend


# Type-only import for AbstractContextManager (kept lazy for older Pythons).
try:
    from contextlib import AbstractContextManager  # noqa: F401
except ImportError:  # pragma: no cover
    AbstractContextManager = object  # type: ignore
