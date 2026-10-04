"""Interfaces for every external service, plus offline fakes. PRE-IMPLEMENTED.

RULE (tests/invariants/test_network_boundary.py): only modules in satyapan/adapters/ may
import network libraries (boto3, httpx, requests, urllib.request, socket). Everything else
receives an adapter object, so unit tests can pass a fake.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class TranscriptResult:
    text: str
    language: str = "unknown"  # "hi", "en", "unknown"
    duration_s: float = 0.0
    engine: str = "unknown"


class Transcriber(Protocol):
    def transcribe(
        self, audio: bytes, mime: str, language_hint: str | None = None
    ) -> TranscriptResult: ...


class LLMClient(Protocol):
    def complete(self, system: str, user: str, max_tokens: int) -> str:
        """Return model text. Must raise TimeoutError after settings.aws_timeout_s."""
        ...


class Mailer(Protocol):
    def send(self, to: str, subject: str, body: str) -> str:
        """Send an email; return a message id. Raise on failure (caller falls back)."""
        ...


# ---------------- Fakes for tests and offline demo ----------------


@dataclass
class FakeTranscriber:
    """Returns pre-set texts in order (one per call). Used by T11/T17 tests."""

    texts: list[str]
    language: str = "hi"
    calls: int = 0

    def transcribe(
        self, audio: bytes, mime: str, language_hint: str | None = None
    ) -> TranscriptResult:
        text = self.texts[min(self.calls, len(self.texts) - 1)]
        self.calls += 1
        return TranscriptResult(text=text, language=self.language, duration_s=10.0, engine="fake")


@dataclass
class FakeLLM:
    """Returns a fixed reply. Used by T15 tests (including injection red-team tests)."""

    reply: str
    last_system: str | None = None
    last_user: str | None = None

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        self.last_system, self.last_user = system, user
        return self.reply


@dataclass
class InAppMailer:
    """Local fallback for SES: stores messages so the CFO's console screen can show them."""

    outbox: list[dict[str, str]] = field(default_factory=list)

    def send(self, to: str, subject: str, body: str) -> str:
        msg_id = f"inapp-{len(self.outbox) + 1}"
        self.outbox.append({"id": msg_id, "to": to, "subject": subject, "body": body})
        return msg_id
