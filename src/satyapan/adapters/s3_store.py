"""Amazon S3 evidence store + Object Lock anchors (ap-south-1). TASK T09.

See docs/tasks/T09-evidence-vault.md. boto3 is an optional extra: `uv sync --extra aws`.
Every call uses a 5 s timeout (settings.aws_timeout_s); callers fall back to LocalStorage.
"""

from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlparse

from satyapan.contracts.common import utcnow
from satyapan.settings import Settings


class S3Storage:
    """BlobStore backed by S3. put() returns "s3://<bucket>/<key>".

    Anchors are written with ObjectLockMode="GOVERNANCE" and a 1-day RetainUntilDate.
    The app's IAM role may PutObject but not DeleteObject (see docs/ARCHITECTURE.md §9).
    """

    def __init__(self, settings: Settings) -> None:
        # boto3 is optional: import it only when AWS mode is actually on, so the app and the
        # unit tests import this module safely without the extra installed.
        import boto3  # noqa: PLC0415
        from botocore.config import Config  # noqa: PLC0415

        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            config=Config(
                connect_timeout=settings.aws_timeout_s,
                read_timeout=settings.aws_timeout_s,
                retries={"max_attempts": 1},
            ),
        )

    @staticmethod
    def _check_key(key: str) -> None:
        if not key or key.startswith("/") or ".." in key.split("/"):
            raise ValueError(f"unsafe storage key: {key!r}")

    def put(self, key: str, data: bytes, media_type: str) -> str:
        self._check_key(key)
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=media_type,
            ServerSideEncryption="AES256",
        )
        return f"s3://{self.bucket}/{key}"

    def get(self, uri: str) -> bytes:
        parsed = urlparse(uri)
        if parsed.scheme != "s3" or not parsed.netloc:
            raise ValueError(f"S3Storage cannot read {uri!r}; expected s3://bucket/key")
        body = self.client.get_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))
        return bytes(body["Body"].read())

    def put_locked(self, key: str, data: bytes, retain_days: int = 1) -> str:
        """PutObject with Object Lock GOVERNANCE retention (anchors only)."""
        self._check_key(key)
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType="application/json",
            ServerSideEncryption="AES256",
            ObjectLockMode="GOVERNANCE",
            ObjectLockRetainUntilDate=utcnow() + timedelta(days=retain_days),
        )
        return f"s3://{self.bucket}/{key}"
