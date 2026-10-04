"""Amazon SES mailer for OOB-Confirm emails (sandbox, verified team addresses). TASK T12.

See docs/tasks/T12-oob-confirm.md. Fallback: satyapan.adapters.base.InAppMailer.
"""

from __future__ import annotations

from satyapan.settings import Settings


class SesMailer:
    """Mailer backed by SES v2 SendEmail in settings.aws_region (ap-south-1)."""

    def __init__(self, settings: Settings) -> None:
        raise NotImplementedError("T12: see docs/tasks/T12-oob-confirm.md")

    def send(self, to: str, subject: str, body: str) -> str:
        raise NotImplementedError("T12: see docs/tasks/T12-oob-confirm.md")
