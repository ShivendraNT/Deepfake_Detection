"""Parse a raw .eml into a ParsedEmail. TASK T03 — see docs/tasks/T03-eml-parser.md.

Use only the Python standard library (`email`, `email.policy.default`). Deterministic.
"""

from __future__ import annotations

import email
import email.policy
import email.utils
import hashlib
import html
import re
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import get_args

from satyapan.contracts.parsed import AttachmentMeta, AuthResults, AuthVerdict, ParsedEmail

DETECTOR_NAME = "email_parser"
DETECTOR_VERSION = "0.1.0"

_VERDICTS = frozenset(get_args(AuthVerdict))
_VERDICT_RE = re.compile(r"\b(spf|dkim|dmarc)=(\w+)")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
# An element whose style hides it, together with its inner text (the prompt-injection hiding spot).
_HIDDEN_BLOCK_RE = re.compile(
    r"<(?P<tag>[a-z0-9]+)\b[^>]*?\bstyle\s*=\s*(?P<q>['\"])[^'\"]*"
    r"(?:display\s*:\s*none|visibility\s*:\s*hidden)[^'\"]*(?P=q)[^>]*>"
    r".*?(?:</\s*(?P=tag)\s*>|(?=</)|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]*>")
_SPACE_RE = re.compile(r"\s+")


def parse_eml(raw: bytes, *, trusted_authserv_id: str) -> ParsedEmail:
    """Parse headers, body text and attachment metadata.

    - from_addr / from_domain from the From header (lower-cased domain).
    - reply_to_domain / return_path_domain: domains of Reply-To and Return-Path, or None.
    - auth: parse_auth_results(all Authentication-Results header values, trusted_authserv_id).
    - body_text: the text/plain part; if only HTML exists, strip tags AND <!-- comments -->
      AND elements styled display:none (attackers hide prompt injections there).
    - attachments: AttachmentMeta for each attachment (sha256 of the decoded bytes).
    Raise ValueError if there is no From header (caller turns it into GreyReason.PARSE_FAILURE).
    """
    msg: EmailMessage = email.message_from_bytes(raw, policy=email.policy.default)

    from_header = msg.get("From")
    if from_header is None:
        raise ValueError("T03: email has no From header")
    from_display_name, from_addr = email.utils.parseaddr(str(from_header))
    from_parts = _split_address(from_addr)
    if from_parts is None:
        raise ValueError(f"T03: From header has no address with a domain: {from_addr!r}")
    from_addr, from_domain = from_parts

    auth = parse_auth_results(
        [str(v) for v in msg.get_all("Authentication-Results", [])], trusted_authserv_id
    )
    to_addrs = [
        addr
        for _, addr in email.utils.getaddresses([str(v) for v in msg.get_all("To", [])])
        if addr
    ]
    message_id = msg.get("Message-ID")
    subject = msg.get("Subject")

    return ParsedEmail(
        message_id=str(message_id) if message_id is not None else None,
        subject=str(subject) if subject is not None else "",
        from_addr=from_addr,
        from_display_name=str(from_display_name).strip(),
        from_domain=from_domain,
        reply_to_domain=_header_domain(msg.get("Reply-To")),
        return_path_domain=_header_domain(msg.get("Return-Path")),
        to=to_addrs,
        date=_parse_date(msg.get("Date")),
        auth=auth,
        body_text=_body_text(msg),
        attachments=[
            AttachmentMeta(
                filename=filename,
                media_type=media_type,
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
            )
            for filename, media_type, data in _attachment_parts(msg)
        ],
    )


def parse_auth_results(header_values: list[str], trusted_authserv_id: str) -> AuthResults:
    """Use ONLY the TOPMOST Authentication-Results header whose authserv-id equals
    `trusted_authserv_id` (the header our own receiving MTA adds). All other
    Authentication-Results headers are attacker-controllable: count them in
    untrusted_headers_seen and ignore their verdicts.

    Example trusted value:
      "mx.demo-industries.example; spf=pass smtp.mailfrom=kaveri-packaging.example;
       dkim=pass header.d=kaveri-packaging.example; dmarc=pass header.from=kaveri-packaging.example"
    -> AuthResults(authserv_id="mx.demo-industries.example", spf="pass", dkim="pass",
                   dmarc="pass", trusted=True)
    No trusted header -> AuthResults(trusted=False) with verdicts "unknown".
    """
    wanted = trusted_authserv_id.strip().lower()
    trusted_value: str | None = None
    untrusted_headers_seen = 0
    for value in header_values:
        text = str(value)
        authserv_id = text.split(";", 1)[0].strip().lower()
        if trusted_value is None and authserv_id == wanted:
            trusted_value = text
        else:
            untrusted_headers_seen += 1
    if trusted_value is None:
        return AuthResults(trusted=False, untrusted_headers_seen=untrusted_headers_seen)

    verdicts = {"spf": "unknown", "dkim": "unknown", "dmarc": "unknown"}
    for match in _VERDICT_RE.finditer(trusted_value):
        key = match.group(1).lower()
        value = match.group(2).lower()
        if verdicts[key] == "unknown" and value in _VERDICTS:
            verdicts[key] = value
    return AuthResults(
        authserv_id=trusted_value.split(";", 1)[0].strip(),
        spf=verdicts["spf"],
        dkim=verdicts["dkim"],
        dmarc=verdicts["dmarc"],
        trusted=True,
        untrusted_headers_seen=untrusted_headers_seen,
    )


def extract_attachments(raw: bytes) -> list[tuple[str | None, str, bytes]]:
    """Return (filename, media_type, decoded_bytes) for each attachment part."""
    msg: EmailMessage = email.message_from_bytes(raw, policy=email.policy.default)
    return _attachment_parts(msg)


def _attachment_parts(msg: EmailMessage) -> list[tuple[str | None, str, bytes]]:
    """Decoded (filename, media_type, bytes) for every attachment of a parsed message."""
    if not msg.is_multipart():
        return []
    parts: list[tuple[str | None, str, bytes]] = []
    for part in msg.iter_attachments():
        content = part.get_content()
        if isinstance(content, bytes):
            data = content
        elif isinstance(content, str):
            data = content.encode(part.get_content_charset() or "utf-8", errors="replace")
        else:  # a nested message or another multipart: not something we can hash
            continue
        parts.append((part.get_filename(), part.get_content_type(), data))
    return parts


def _split_address(value: str) -> tuple[str, str] | None:
    """(local-part, lower-cased domain) of a single address, or None if it is unusable."""
    local, sep, domain = str(value).strip().strip("<>").strip().rpartition("@")
    if not sep:
        return None
    domain = domain.rstrip(".").lower()
    if not local or not domain or " " in domain:
        return None
    return local, domain


def _header_domain(header: object) -> str | None:
    """Domain of the first address in a header, or None when the header is absent/invalid."""
    if header is None:
        return None
    parts = _split_address(email.utils.parseaddr(str(header))[1])
    return parts[1] if parts else None


def _parse_date(header: object) -> datetime | None:
    if header is None:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(str(header))
    except (TypeError, ValueError):
        return None
    if parsed is None:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _body_text(msg: EmailMessage) -> str:
    """Plain body, or HTML converted to text with comments and hidden elements removed."""
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    content = part.get_content()
    if isinstance(content, bytes):
        content = content.decode(part.get_content_charset() or "utf-8", errors="replace")
    if not isinstance(content, str):
        return ""
    if part.get_content_maintype() == "text" and part.get_content_subtype() == "html":
        return _html_to_text(content)
    return content.strip()


def _html_to_text(source: str) -> str:
    visible = _COMMENT_RE.sub(" ", source)
    visible = _HIDDEN_BLOCK_RE.sub(" ", visible)
    text = html.unescape(_TAG_RE.sub(" ", visible))
    return _SPACE_RE.sub(" ", text).strip()
