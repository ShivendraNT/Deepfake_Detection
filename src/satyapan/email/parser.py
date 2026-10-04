"""Parse a raw .eml into a ParsedEmail. TASK T03 — see docs/tasks/T03-eml-parser.md.

Use only the Python standard library (`email`, `email.policy.default`). Deterministic.
"""

from __future__ import annotations

from satyapan.contracts.parsed import AuthResults, ParsedEmail

DETECTOR_NAME = "email_parser"
DETECTOR_VERSION = "0.1.0"


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
    raise NotImplementedError("T03: see docs/tasks/T03-eml-parser.md")


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
    raise NotImplementedError("T03: see docs/tasks/T03-eml-parser.md")


def extract_attachments(raw: bytes) -> list[tuple[str | None, str, bytes]]:
    """Return (filename, media_type, decoded_bytes) for each attachment part."""
    raise NotImplementedError("T03: see docs/tasks/T03-eml-parser.md")
