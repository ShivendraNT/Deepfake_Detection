"""Blob storage adapters for evidence (C1). TASK T09 — see docs/tasks/T09-evidence-vault.md.

Two backends behind one interface:
- LocalStorage: files under settings.vault_dir (default ./vault_data/). Always works.
- S3Storage: Amazon S3 in ap-south-1 (versioning + SSE). Lives in satyapan/adapters/s3_store.py
  because only adapters may talk to the network.
get_storage() picks S3 when SATYAPAN_AWS_MODE=on and a bucket is set, else LocalStorage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from satyapan.settings import Settings


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

    def put(self, key: str, data: bytes, media_type: str) -> str:
        """Write `data` to root/key (create parent dirs) and return 'file://<absolute path>'.

        Must raise ValueError if `key` contains '..' or starts with '/'.
        """
        raise NotImplementedError("T09: see docs/tasks/T09-evidence-vault.md")

    def get(self, uri: str) -> bytes:
        """Read the file behind a 'file://' URI. Raise ValueError for other schemes."""
        raise NotImplementedError("T09: see docs/tasks/T09-evidence-vault.md")


def get_storage(settings: Settings) -> BlobStore:
    """Return S3Storage if settings.aws_mode and settings.s3_bucket, else LocalStorage.

    If creating the S3 client fails, log a warning and return LocalStorage (fallback).
    """
    raise NotImplementedError("T09: see docs/tasks/T09-evidence-vault.md")
