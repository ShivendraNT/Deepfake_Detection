"""Amazon S3 evidence store + Object Lock anchors (ap-south-1). TASK T09.

See docs/tasks/T09-evidence-vault.md. boto3 is an optional extra: `uv sync --extra aws`.
Every call uses a 5 s timeout (settings.aws_timeout_s); callers fall back to LocalStorage.
"""

from __future__ import annotations

from satyapan.settings import Settings


class S3Storage:
    """BlobStore backed by S3. put() returns "s3://<bucket>/<key>".

    Anchors are written with ObjectLockMode="GOVERNANCE" and a 1-day RetainUntilDate.
    The app's IAM role may PutObject but not DeleteObject (see docs/ARCHITECTURE.md §9).
    """

    def __init__(self, settings: Settings) -> None:
        raise NotImplementedError("T09: see docs/tasks/T09-evidence-vault.md")

    def put(self, key: str, data: bytes, media_type: str) -> str:
        raise NotImplementedError("T09: see docs/tasks/T09-evidence-vault.md")

    def get(self, uri: str) -> bytes:
        raise NotImplementedError("T09: see docs/tasks/T09-evidence-vault.md")

    def put_locked(self, key: str, data: bytes, retain_days: int = 1) -> str:
        """PutObject with Object Lock GOVERNANCE retention (anchors only)."""
        raise NotImplementedError("T09: see docs/tasks/T09-evidence-vault.md")
