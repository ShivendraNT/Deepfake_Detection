"""Amazon SES mailer for OOB-Confirm emails (sandbox, verified team addresses). TASK T12.

See docs/tasks/T12-oob-confirm.md. Fallback: satyapan.adapters.base.InAppMailer.
"""

from __future__ import annotations

from satyapan.settings import Settings


class SesMailer:
    """Mailer backed by SES v2 SendEmail in settings.aws_region (ap-south-1)."""

    def __init__(self, settings: Settings) -> None:
        # boto3 is an optional extra (`uv sync --extra aws`): import it only when AWS mode
        # is actually on, so importing this module never needs the extra installed.
        import boto3  # type: ignore[import-not-found]  # noqa: PLC0415
        from botocore.config import Config  # type: ignore[import-not-found]  # noqa: PLC0415

        self.sender = settings.ses_sender
        self.client = boto3.client(
            "sesv2",
            region_name=settings.aws_region,
            config=Config(
                connect_timeout=settings.aws_timeout_s,
                read_timeout=settings.aws_timeout_s,
                retries={"max_attempts": 1},
            ),
        )

    def send(self, to: str, subject: str, body: str) -> str:
        """Send a plain-text email. Raises on failure (the caller falls back to in-app)."""
        response = self.client.send_email(
            FromEmailAddress=self.sender,
            Destination={"ToAddresses": [to]},
            Content={
                "Simple": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
                }
            },
        )
        return str(response["MessageId"])
