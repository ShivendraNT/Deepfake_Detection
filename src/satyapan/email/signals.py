"""Turn a ParsedEmail into Signals. TASK T04 — see docs/tasks/T04-domain-checks.md.

Every signal is built with Signal.make(code, source=SignalSource.DETERMINISTIC, ...).
"""

from __future__ import annotations

from typing import Any

from satyapan.contracts.enums import GreyReason, ReasonCode, SignalSource
from satyapan.contracts.evidence import DetectorOutput, Signal
from satyapan.contracts.parsed import ParsedEmail
from satyapan.email.domains import claims_to_be_bank, is_bank_in, is_freemail, is_lookalike
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
    signals: list[Signal] = []
    grey_reasons: list[GreyReason] = []

    def add(code: ReasonCode, detail: dict[str, Any] | None = None) -> None:
        signals.append(
            Signal.make(
                code,
                source=SignalSource.DETERMINISTIC,
                evidence_ids=[evidence_id],
                detector=DETECTOR_NAME,
                detail=detail,
            )
        )

    if not parsed.auth.trusted:
        grey_reasons.append(GreyReason.PARSE_FAILURE)
    elif parsed.auth.dmarc == "fail":
        add(ReasonCode.EMAIL_DMARC_FAIL, {"dmarc": "fail"})

    imitates = is_lookalike(parsed.from_domain, master.known_domains())
    if imitates:
        add(ReasonCode.EMAIL_LOOKALIKE_DOMAIN, {"imitates": imitates})

    if claims_to_be_bank(parsed.from_display_name, parsed.from_domain) and not is_bank_in(
        parsed.from_domain
    ):
        add(ReasonCode.EMAIL_BANK_NOT_BANK_IN)

    mismatches = [
        domain
        for domain in (parsed.reply_to_domain, parsed.return_path_domain)
        if domain is not None and domain != parsed.from_domain and domain not in KNOWN_ESP_DOMAINS
    ]
    if mismatches:
        add(
            ReasonCode.EMAIL_REPLYTO_MISMATCH,
            {"other_domains": ", ".join(sorted(set(mismatches)))},
        )

    if is_freemail(parsed.from_domain):
        claim = _known_identity_claim(parsed, master)
        if claim:
            add(ReasonCode.EMAIL_FREEMAIL_CORPORATE, {"claims": claim})

    if not signals and parsed.auth.trusted and parsed.auth.dmarc == "pass":
        add(ReasonCode.EMAIL_AUTH_PASS)

    return DetectorOutput(
        detector=DETECTOR_NAME,
        version=DETECTOR_VERSION,
        evidence_id=evidence_id,
        signals=signals,
        grey_reasons=grey_reasons,
        artifacts={"from_domain": parsed.from_domain, "dmarc": parsed.auth.dmarc},
    )


def _known_identity_claim(parsed: ParsedEmail, master: MasterData) -> str | None:
    """What a free-mail sender pretends to be: a known employee, our company or a vendor."""
    text = f"{parsed.from_display_name} {parsed.subject}".lower()
    for employee in master.employees.values():
        if employee.name and employee.name.lower() in text:
            return employee.name
    company = master.company_domain.split(".")[0].replace("-", " ").strip()
    if company and company in text:
        return company
    for vendor in master.vendors.values():
        if vendor.legal_name and vendor.legal_name.lower() in text:
            return vendor.legal_name
    return None
