"""Turn a ParsedEmail into Signals. TASK T04 — see docs/tasks/T04-domain-checks.md.

Every signal is built with Signal.make(code, source=SignalSource.DETERMINISTIC, ...).
"""

from __future__ import annotations

from satyapan.contracts.evidence import DetectorOutput
from satyapan.contracts.parsed import ParsedEmail
from satyapan.master.store import MasterData

DETECTOR_NAME = "email_checker"
DETECTOR_VERSION = "0.1.0"

# Reply-To/Return-Path domains of known email service providers (bounce handling).
KNOWN_ESP_DOMAINS: frozenset[str] = frozenset(
    {"amazonses.com", "sendgrid.net", "mailgun.org", "mcsv.net", "sparkpostmail.com"}
)


def email_signals(parsed: ParsedEmail, master: MasterData, evidence_id: str) -> DetectorOutput:
    """Rules (each at most once):
    - auth.trusted and auth.dmarc == "fail"                 -> EMAIL_DMARC_FAIL
    - not auth.trusted                                       -> grey_reasons += [PARSE_FAILURE]
    - is_lookalike(from_domain, master.known_domains())      -> EMAIL_LOOKALIKE_DOMAIN
      (detail: {"imitates": <known domain>})
    - claims_to_be_bank(from_display_name, from_domain)
      and not is_bank_in(from_domain) -> EMAIL_BANK_NOT_BANK_IN
    - reply_to/return_path domain != from_domain and not in KNOWN_ESP_DOMAINS
                                                             -> EMAIL_REPLYTO_MISMATCH
    - is_freemail(from_domain) and display name/subject claims a company or a known
      employee name                                          -> EMAIL_FREEMAIL_CORPORATE
    - if none of the raising rules fired and dmarc == "pass" -> EMAIL_AUTH_PASS (info only)
    Return DetectorOutput(detector=DETECTOR_NAME, version=DETECTOR_VERSION,
                          evidence_id=evidence_id, signals=[...], grey_reasons=[...],
                          artifacts={"from_domain": ..., "dmarc": ...}).
    """
    raise NotImplementedError("T04: see docs/tasks/T04-domain-checks.md")
