"""Blob storage adapters for evidence (C1). TASK T09 — see docs/tasks/T09-evidence-vault.md.

Two backends behind one interface:
- LocalStorage: files under settings.vault_dir (default ./vault_data/). Always works.
- S3Storage: Amazon S3 in ap-south-1 (versioning + SSE). Lives in satyapan/adapters/s3_store.py
  because only adapters may talk to the network.
get_storage() picks S3 when SATYAPAN_AWS_MODE=on and a bucket is set, else LocalStorage.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Protocol
from urllib.parse import unquote, urlparse

from satyapan.settings import Settings

log = logging.getLogger(__name__)

_DRIVE_OR_SEP = re.compile(r"^(?:[A-Za-z]:)?(?:[\\/]|$)")


class BlobStore(Protocol):
    def put(self, key: str, data: bytes, media_type: str) -> str:
        """Store bytes under `key`; return a URI ("file://..." or "s3://bucket/key")."""
        ...

    def get(self, uri: str) -> bytes:
        """Read bytes back from a URI returned by put()."""
        ...


class LocalStorage:
    """Stores blobs as files under `root`. Keys may contain '/', never '..'."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _target(self, key: str) -> Path:
        """Safe path for `key`, always inside `root`. Raises ValueError otherwise."""
        if not key or _DRIVE_OR_SEP.match(key) or ".." in key.split("/"):
            raise ValueError(f"unsafe storage key: {key!r}")
        root = self.root.resolve()
        target = (root / key.replace("\\", "/")).resolve()
        if not target.is_relative_to(root):
            raise ValueError(f"key escapes the vault root: {key!r}")
        return target

    def put(self, key: str, data: bytes, media_type: str) -> str:
        """Write `data` to root/key (create parent dirs) and return 'file://<absolute path>'.

        Must raise ValueError if `key` contains '..' or starts with '/'.
        """
        path = self._target(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path.resolve().as_uri()

    def get(self, uri: str) -> bytes:
        """Read the file behind a 'file://' URI. Raise ValueError for other schemes."""
        parsed = urlparse(uri)
        if parsed.scheme != "file":
            raise ValueError(f"LocalStorage cannot read {parsed.scheme or 'relative'} URIs")
        if parsed.netloc not in ("", "localhost"):
            raise ValueError(f"unsupported file URI host: {parsed.netloc!r}")
        raw = unquote(parsed.path)
        if os.name == "nt" and len(raw) > 2 and raw[0] == "/" and raw[2] == ":":
            raw = raw[1:]  # file:///C:/... -> C:/...
        path = Path(raw).resolve()
        root = self.root.resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"URI escapes the vault root: {uri!r}")
        return path.read_bytes()


def get_storage(settings: Settings) -> BlobStore:
    """Return S3Storage if settings.aws_mode and settings.s3_bucket, else LocalStorage.

    If creating the S3 client fails, log a warning and return LocalStorage (fallback).
    """
    if settings.aws_mode and settings.s3_bucket:
        try:
            from satyapan.adapters.s3_store import S3Storage

            return S3Storage(settings)
        except Exception as exc:  # noqa: BLE001 — any AWS problem must fall back, never crash
            log.warning("S3 storage unavailable (%s); falling back to local vault", exc)
    return LocalStorage(settings.vault_dir)
