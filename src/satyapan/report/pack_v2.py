"""Golden-hour report pack v2 (F11) — five drafts a human reviews and sends.

`build_report_pack_v2` is pure: it reads the case, the trusted master, the custody rows and a
timestamp, and returns the frozen `ReportPackV2` contract. It never opens a socket and never
files anything; every section is `DRAFT_REQUIRES_HUMAN_REVIEW` and the pack is `MANUAL_ONLY`.

Only `src/satyapan/policy/` may set a band. This module has no band, no score and no network.
"""

from __future__ import annotations

import re
from datetime import datetime
from string import ascii_letters, digits

from satyapan.api.companion.models import ReportField, ReportPackV2, ReportSection
from satyapan.contracts.case import Case
from satyapan.contracts.custody import CustodyRow
from satyapan.contracts.evidence import Evidence
from satyapan.contracts.report import TransactionFacts
from satyapan.master.store import MasterData
from satyapan.report.pack import (
    _bank_email,
    _call_script_1930,
    _fmt_when,
    _transaction_facts,
    format_inr,
)

_SAFE_URL_CHARS = set(ascii_letters + digits + "-._~")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

_CERT_IN_DEADLINE = (
    "Within 6 hours of noticing (CERT-In Directions, 2022) — confirm with your IT/legal team"
)
_CERT_IN_TYPE = "Identity theft, spoofing and phishing attacks"

_BSA_PART_A = (
    "PART A\n"
    "[See section 63(4)]\n"
    "Certificate of the person in charge of the computer or communication device or the "
    "management of the relevant activities (whichever is appropriate)\n\n"
    "I, ______________________, hereby certify that:\n"
    "(a) the electronic record, namely {case_id} evidence pack, containing the details of the "
    "relevant electronic record, was produced by the computer or communication device or the "
    "management of the relevant activities (whichever is appropriate) in the ordinary course of "
    "the said activities;\n"
    "(b) the computer or communication device or the management of the relevant activities "
    "(whichever is appropriate) was operating properly during the material part of the relevant "
    "period;\n"
    "(c) the electronic record was produced by the computer or communication device or the "
    "management of the relevant activities (whichever is appropriate) in the ordinary course of "
    "the said activities;\n"
    "(d) the hash value of the electronic record is {hashes} and the algorithm used to generate "
    "the hash value is SHA256;\n"
    "(e) the electronic record has not been altered in any manner since the time it was "
    "produced; and\n"
    "(f) I have lawful control over the computer or communication device or the management of "
    "the relevant activities (whichever is appropriate).\n\n"
    "Device / computer particulars: ______________________________________________________\n\n"
    "Signature ______________________\n"
    "Name ______________________\n"
    "Designation ______________________\n"
    "Date ______________________\n"
    "Place ______________________\n\n"
    "Draft prepared by {generated_by} on {generated_at}. This is a draft for the company's own "
    "custodian to review and sign; it has not been filed or signed by Satya."
)


def _field(
    label: str,
    value: str,
    source: str,
    *,
    evidence_id: str | None = None,
    sensitive: bool = False,
    copy: bool = True,
) -> ReportField:
    return ReportField(
        label=label,
        value=value,
        source=source,  # type: ignore[arg-type]
        evidence_id=evidence_id,
        sensitive=sensitive,
        copy=copy,
    )


def _pct(value: str) -> str:
    """Minimal RFC 3986 percent-encoding (report/ may not import urllib)."""
    out: list[str] = []
    for byte in value.encode("utf-8"):
        char = chr(byte)
        if char in _SAFE_URL_CHARS:
            out.append(char)
        else:
            out.append(f"%{byte:02X}")
    return "".join(out)


def _ifsc_upi(facts: TransactionFacts) -> str:
    parts: list[str] = []
    if facts.beneficiary_ifsc:
        parts.append(f"IFSC {facts.beneficiary_ifsc}")
    if facts.beneficiary_upi:
        parts.append(f"UPI {facts.beneficiary_upi}")
    return " / ".join(parts) or "Not available"


def _beneficiary(facts: TransactionFacts) -> str:
    if facts.beneficiary_account:
        return f"{facts.beneficiary_name} (a/c {facts.beneficiary_account})"
    if facts.beneficiary_upi:
        return f"{facts.beneficiary_name} (UPI {facts.beneficiary_upi})"
    return facts.beneficiary_name


def _platform_channel(case: Case) -> str:
    channels = sorted({evidence.channel.value for evidence in case.evidence})
    return ", ".join(channels) if channels else "Online / Email"


def _suspect_identifiers(facts: TransactionFacts) -> str:
    parts: list[str] = []
    if facts.beneficiary_account:
        parts.append(f"Account: {facts.beneficiary_account}")
    if facts.beneficiary_ifsc:
        parts.append(f"IFSC: {facts.beneficiary_ifsc}")
    if facts.beneficiary_upi:
        parts.append(f"UPI: {facts.beneficiary_upi}")
    if facts.beneficiary_bank:
        parts.append(f"Bank: {facts.beneficiary_bank}")
    return ", ".join(parts) if parts else facts.beneficiary_name


def _transaction_table(facts: TransactionFacts) -> str:
    return (
        f"UTR: {facts.utr or 'Pending'} | "
        f"Amount: {format_inr(facts.amount_inr)} | "
        f"Date: {_fmt_when(facts.sent_at, 'N/A')} | "
        f"Rail: {facts.rail}"
    )


def _custody_hash(evidence: Evidence, custody_rows: list[CustodyRow]) -> str:
    """Hash recorded in custody for this evidence, falling back to the vault's intake hash."""
    for row in reversed(custody_rows):
        if row.evidence_id != evidence.id:
            continue
        recorded = row.payload.get("sha256")
        if isinstance(recorded, str) and _HEX64.fullmatch(recorded):
            return recorded
    return evidence.sha256


def _helpline_section(case: Case, facts: TransactionFacts) -> ReportSection:
    body = _call_script_1930(case, facts)
    fields = [
        _field("UTR", facts.utr or "Not available", "maker_entered"),
        _field("Amount", format_inr(facts.amount_inr), "maker_entered"),
        _field("Date and time", _fmt_when(facts.sent_at, "Not available"), "maker_entered"),
        _field(
            "Debit account (masked)",
            facts.debit_account_masked,
            "maker_entered",
            sensitive=True,
        ),
        _field(
            "Beneficiary account",
            facts.beneficiary_account or "Not available",
            "maker_entered",
            sensitive=True,
        ),
        _field("IFSC / UPI", _ifsc_upi(facts), "maker_entered"),
        _field("Beneficiary bank", facts.beneficiary_bank or "Not available", "maker_entered"),
    ]
    return ReportSection(
        id="helpline_1930",
        title="1930 helpline call script",
        destination="1930 helpline (CFCFRMS)",
        deadline_hint="Call now — the golden hour starts with this call",
        body=body,
        fields=fields,
        open_url="tel:1930",
    )


def _bank_section(
    case: Case,
    master: MasterData,
    facts: TransactionFacts,
    generated_by: str,
) -> ReportSection:
    email = _bank_email(case, master, facts, generated_by)
    fields = [
        _field("To", email.to_hint, "system"),
        _field("Subject", email.subject, "system"),
        _field("UTR", facts.utr or "Not available", "maker_entered"),
        _field("Amount", format_inr(facts.amount_inr), "maker_entered"),
        _field(
            "Beneficiary",
            _beneficiary(facts),
            "maker_entered",
            sensitive=bool(facts.beneficiary_account or facts.beneficiary_upi),
        ),
    ]
    open_url = f"mailto:?subject={_pct(email.subject)}&body={_pct(email.body)}"
    return ReportSection(
        id="bank_fraud_desk",
        title="Bank fraud desk email",
        destination="Your bank's fraud desk",
        deadline_hint="Send now — ask the bank to hold or recall the funds",
        body=email.body,
        fields=fields,
        open_url=open_url,
    )


def _ncrp_section(case: Case, facts: TransactionFacts) -> ReportSection:
    description = (
        f"Financial cyber fraud incident under case {case.id}. "
        f"Unauthorized transfer of {format_inr(facts.amount_inr)} to "
        f"{facts.beneficiary_name} via {facts.rail}."
    )
    fields = [
        _field("Incident date/time", _fmt_when(facts.sent_at, "N/A"), "maker_entered"),
        _field("Category", "Online Financial Fraud", "system"),
        _field("Platform/channel", _platform_channel(case), "system"),
        _field(
            "Suspect identifiers",
            _suspect_identifiers(facts),
            "maker_entered",
            sensitive=True,
        ),
        _field("Transaction table", _transaction_table(facts), "maker_entered"),
        _field("Description", description, "system"),
    ]
    for evidence in case.evidence:
        name = evidence.filename or evidence.id
        fields.append(
            _field(
                f"Evidence — {name}",
                f"{name} — SHA-256 {evidence.sha256}",
                "vault",
                evidence_id=evidence.id,
            )
        )
    body = (
        "How to file this on the NCRP portal (a human must file it):\n"
        "1. Open https://cybercrime.gov.in and choose 'Report Cyber Crime Related to "
        "Financial Fraud'.\n"
        "2. Log in with your own mobile number and OTP.\n"
        "3. Copy each field below in the portal's order and attach the evidence listed.\n"
        "4. Note the acknowledgement number and share it with your bank and 1930.\n\n"
        "Draft only — nothing has been submitted by Satya."
    )
    return ReportSection(
        id="ncrp_portal",
        title="NCRP complaint draft",
        destination="cybercrime.gov.in (NCRP)",
        deadline_hint="File before the golden hour closes",
        body=body,
        fields=fields,
        open_url="https://cybercrime.gov.in",
    )


def _cert_in_section(
    case: Case,
    facts: TransactionFacts,
    body_corporate: bool,
) -> ReportSection:
    time_noticed = _fmt_when(facts.sent_at, "To be completed by the reporter")
    systems = _platform_channel(case)
    description = (
        f"Financial cyber fraud under case {case.id}: "
        f"{format_inr(facts.amount_inr)} sent via {facts.rail} to "
        f"{facts.beneficiary_name} after impersonation / spoofing."
    )
    actions = (
        "Paused further payments, preserved evidence with SHA-256 hashes, and prepared drafts "
        "for 1930, the bank fraud desk and NCRP. Review before sending."
    )
    contact = (
        "Name / role / phone / email of the reporting contact (to be completed by the reporter)"
    )
    fields = [
        _field("Incident type", _CERT_IN_TYPE, "system"),
        _field("Time noticed", time_noticed, "maker_entered"),
        _field("Systems affected", systems, "system"),
        _field("Description", description, "system"),
        _field("Actions taken", actions, "system"),
        _field("Contact", contact, "system"),
    ]
    body = (
        "CERT-In incident report (draft — confirm applicability with your IT/legal team)\n"
        f"Incident type: {_CERT_IN_TYPE}\n"
        f"Time noticed: {time_noticed}\n"
        f"Systems affected: {systems}\n"
        f"Description: {description}\n"
        f"Actions taken: {actions}\n"
        f"Contact: {contact}\n\n"
        "Draft only — a human must review and send this email."
    )
    return ReportSection(
        id="cert_in",
        title="CERT-In incident email",
        destination="CERT-In (incident@cert-in.org.in)",
        deadline_hint=_CERT_IN_DEADLINE,
        body=body,
        fields=fields,
        open_url="mailto:incident@cert-in.org.in",
        applies=body_corporate,
    )


def _bsa_section(
    case: Case,
    custody_rows: list[CustodyRow],
    now: datetime,
    generated_by: str,
) -> ReportSection:
    fields: list[ReportField] = []
    hash_lines: list[str] = []
    for evidence in case.evidence:
        name = evidence.filename or evidence.id
        digest = _custody_hash(evidence, custody_rows)
        hash_lines.append(f"{name} ({evidence.id}): {digest} — algorithm SHA256")
        fields.extend(
            [
                _field(
                    f"Electronic record — {name}",
                    f"{name} ({evidence.channel.value}) — case {case.id}",
                    "vault",
                    evidence_id=evidence.id,
                ),
                _field(
                    f"Hash value — {name}",
                    digest,
                    "vault",
                    evidence_id=evidence.id,
                ),
                _field(f"Algorithm used to generate the hash value — {name}", "SHA256", "system"),
            ]
        )
    fields.extend(
        [
            _field(
                "Computer / communication device particulars",
                "________________ (to be completed by the custodian)",
                "system",
            ),
            _field(
                "Lawful control statement",
                "________________ (custodian to confirm: I have lawful control over the "
                "computer or communication device or the management of the relevant activities)",
                "system",
            ),
            _field(
                "Part A signatory",
                "Signature: ________________  Name: ________________  "
                "Designation: ________________  Date: ________________  Place: ________________",
                "system",
            ),
        ]
    )
    hashes = "; ".join(hash_lines) if hash_lines else "no electronic records attached"
    body = _BSA_PART_A.format(
        case_id=case.id,
        hashes=hashes,
        generated_by=generated_by,
        generated_at=_fmt_when(now, "N/A"),
    )
    return ReportSection(
        id="bsa_s63_part_a",
        title="BSA Section 63 certificate — Part A draft",
        destination="Company's own system custodian / court submission",
        deadline_hint=None,
        body=body,
        fields=fields,
        open_url=None,
    )


def build_report_pack_v2(
    case: Case,
    master: MasterData,
    custody_rows: list[CustodyRow],
    now: datetime,
    *,
    body_corporate: bool = True,
    generated_by: str = "satya",
) -> ReportPackV2:
    """Turn a confirmed-fraud case into the five Report Copilot drafts, in checklist order.

    - Facts come from `case.txn` (maker-entered, trusted) via `pack._transaction_facts`.
    - The 1930 script and bank email reuse the existing T16 helpers, so the UTR stays first.
    - Every field cites its source; account numbers are `sensitive`; evidence fields carry
      their vault evidence id and SHA-256.
    - The pack is `MANUAL_ONLY` with `auto_submit=False`; a human sends every section.
    """
    facts = _transaction_facts(case)
    sections = [
        _helpline_section(case, facts),
        _bank_section(case, master, facts, generated_by),
        _ncrp_section(case, facts),
        _cert_in_section(case, facts, body_corporate),
        _bsa_section(case, custody_rows, now, generated_by),
    ]
    return ReportPackV2(
        case_id=case.id,
        generated_at=now,
        money_left_at=facts.sent_at,
        sections=sections,
    )
