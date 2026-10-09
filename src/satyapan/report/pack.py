"""Build the UTR-first report pack. TASK T16 — docs/tasks/T16-report-pack.md.

There is NO public 1930/NCRP API. This module only produces text/JSON/HTML drafts that a
human copies into the portal, reads out on the 1930 call, or emails to the bank.
It must not import any network library (tests/invariants/test_no_auto_reporting.py).
"""

from __future__ import annotations

import html
from datetime import datetime
from typing import Literal

from satyapan.contracts.case import Case
from satyapan.contracts.custody import CustodyRow
from satyapan.contracts.enums import CaseStatus
from satyapan.contracts.report import (
    EmailDraft,
    EvidenceIndexItem,
    NcrpField,
    ReportPack,
    TransactionFacts,
)
from satyapan.master.store import MasterData

Variant = Literal["ATTEMPTED", "MONEY_SENT"]


class ReportNotUnlockedError(PermissionError):
    """The pack is unlocked only by SUSPECTED_FRAUD (ATTEMPTED) or CONFIRMED_FRAUD (MONEY_SENT)."""


def format_inr(amount: int) -> str:
    """Indian digit grouping: 4850000 -> '₹48,50,000'; 620000 -> '₹6,20,000'."""
    sign = "-" if amount < 0 else ""
    digits = str(abs(amount))
    if len(digits) <= 3:
        return f"{sign}₹{digits}"
    head, tail = digits[:-3], digits[-3:]
    groups: list[str] = [tail]
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return f"{sign}₹{','.join(groups)}"


def _fmt_when(sent_at: datetime | None, missing: str) -> str:
    """'04 Oct 2026 16:42' — the exact words a human reads out on the phone."""
    return sent_at.strftime("%d %b %Y %H:%M") if sent_at else missing


def _payee_line(facts: TransactionFacts) -> str:
    """beneficiary a/c <acct>, IFSC <ifsc> / UPI <upi>, bank <bank> — only the parts we have."""
    parts: list[str] = []
    if facts.beneficiary_account:
        parts.append(f"beneficiary a/c {facts.beneficiary_account}")
    if facts.beneficiary_ifsc and facts.beneficiary_upi:
        parts.append(f"IFSC {facts.beneficiary_ifsc} / UPI {facts.beneficiary_upi}")
    elif facts.beneficiary_ifsc:
        parts.append(f"IFSC {facts.beneficiary_ifsc}")
    elif facts.beneficiary_upi:
        parts.append(f"UPI {facts.beneficiary_upi}")
    if facts.beneficiary_bank:
        parts.append(f"bank {facts.beneficiary_bank}")
    return ", ".join(parts) if parts else f"payee {facts.beneficiary_name}"


def _check_unlock(case: Case, variant: Variant, facts: TransactionFacts) -> None:
    if variant == "ATTEMPTED":
        if case.status not in (CaseStatus.SUSPECTED_FRAUD, CaseStatus.CONFIRMED_FRAUD):
            raise ReportNotUnlockedError(
                f"{case.id}: ATTEMPTED pack is locked until the status is SUSPECTED_FRAUD "
                f"or CONFIRMED_FRAUD (now {case.status.value})"
            )
        return
    if case.status is not CaseStatus.CONFIRMED_FRAUD:
        raise ReportNotUnlockedError(
            f"{case.id}: MONEY_SENT pack is locked until the status is CONFIRMED_FRAUD "
            f"(now {case.status.value})"
        )
    if not facts.utr:
        raise ReportNotUnlockedError(
            f"{case.id}: MONEY_SENT pack needs the UTR — add it to the transaction first"
        )


def _transaction_facts(case: Case) -> TransactionFacts:
    """Transaction facts first: this is what freezes money, not the media hashes."""
    txn = case.txn
    if txn is None:
        raise ReportNotUnlockedError(
            f"{case.id}: no transaction on this case, so there is nothing to report"
        )
    return TransactionFacts(
        utr=txn.utr,
        amount_inr=txn.amount_inr,
        sent_at=txn.sent_at,
        rail=str(txn.rail),
        debit_account_masked=txn.debit_account_masked,
        beneficiary_name=txn.beneficiary_name,
        beneficiary_account=txn.account_number,
        beneficiary_ifsc=txn.ifsc,
        beneficiary_upi=txn.upi_id,
        beneficiary_bank=txn.beneficiary_bank,
    )


def _call_script_1930(case: Case, facts: TransactionFacts) -> str:
    """Spoken on the 1930 helpline. Line 1 leads with the UTR — the golden hour starts there."""
    line1 = (
        f"UTR {facts.utr}: I want to report a financial cyber fraud. "
        f"Amount {format_inr(facts.amount_inr)} sent on "
        f"{_fmt_when(facts.sent_at, 'the time on the bank statement')} "
        f"from our bank (a/c {facts.debit_account_masked}) by {facts.rail} "
        f"to {_payee_line(facts)}."
    )
    lines = [
        line1,
        "",
        f"Case reference: {case.id} (report generated as a draft only, nothing has been filed).",
        f"Money left our account on: {_fmt_when(facts.sent_at, 'not yet sent')}.",
        "Please freeze the beneficiary account and return the money under the "
        "golden-hour / ledger-freeze process.",
        "I can share the transaction receipt, the UTR and the file hashes of our evidence "
        "on request.",
    ]
    return "\n".join(lines)


def _bank_email(
    case: Case, master: MasterData, facts: TransactionFacts, generated_by: str
) -> EmailDraft:
    """Subject starts with 'URGENT: fraud' and carries the UTR when we have one."""
    subject_bits = [f"URGENT: fraud — {facts.rail} of {format_inr(facts.amount_inr)}"]
    if facts.utr:
        subject_bits.append(f"UTR {facts.utr}")
    subject_bits.append(f"beneficiary a/c {facts.beneficiary_account or facts.beneficiary_upi}")
    subject = " | ".join(subject_bits)

    vendor = master.vendors.get(case.txn.vendor_id) if case.txn and case.txn.vendor_id else None
    if vendor is None:
        master_note = "No vendor master record matches this beneficiary."
    elif vendor.has_account(
        facts.beneficiary_account, facts.beneficiary_ifsc, facts.beneficiary_upi
    ):
        master_note = "The beneficiary matches the vendor master."
    else:
        master_note = (
            f"The beneficiary does NOT match vendor master {vendor.vendor_id} "
            f"({vendor.legal_name}, registered domain {vendor.email_domain})."
        )

    facts_lines = [
        f"UTR: {facts.utr or 'not available (money has not left yet)'}",
        f"Amount: {format_inr(facts.amount_inr)}",
        f"Sent on: {_fmt_when(facts.sent_at, 'not yet sent')}",
        f"Rail: {facts.rail}",
        f"Our debit a/c: {facts.debit_account_masked}",
        f"Beneficiary name: {facts.beneficiary_name}",
        f"Beneficiary a/c: {facts.beneficiary_account or 'n/a'}",
        f"IFSC: {facts.beneficiary_ifsc or 'n/a'}",
        f"UPI: {facts.beneficiary_upi or 'n/a'}",
        f"Beneficiary bank: {facts.beneficiary_bank or 'n/a'}",
        master_note,
    ]
    evidence_lines = [
        f"- {e.sha256}  {e.filename or e.id}  ({e.channel.value})" for e in case.evidence
    ]
    body = "\n".join(
        [
            "Please freeze / recall the transaction below immediately — this is the "
            "golden hour after a financial cyber fraud.",
            "",
            "TRANSACTION FACTS",
            *[f"- {line}" for line in facts_lines],
            "",
            "WHAT WE ASK THE BANK TO DO",
            "1. Freeze the beneficiary account and recall the funds.",
            "2. Share the beneficiary account holder name and the branch contact.",
            "3. Confirm receipt of this mail on the bank's fraud desk number.",
            "",
            "EVIDENCE ON FILE (SHA-256, available on request)",
            *(evidence_lines or ["- none"]),
            "",
            f"Report reference: {case.id}. Generated by {generated_by} "
            f"({master.company_domain}). Draft only — a human will send this mail.",
        ]
    )
    return EmailDraft(
        to_hint="your bank relationship manager / fraud desk (send from the company's own mail)",
        subject=subject,
        body=body,
    )


def build_report_pack(
    case: Case,
    master: MasterData,
    custody_rows: list[CustodyRow],
    variant: Variant,
    generated_by: str,
    now: datetime,
) -> ReportPack:
    """- ATTEMPTED requires status SUSPECTED_FRAUD or CONFIRMED_FRAUD; MONEY_SENT requires
      CONFIRMED_FRAUD AND txn.utr. Otherwise raise ReportNotUnlockedError.
    - facts: from case.txn (full beneficiary account IS included here: the bank needs it).
    - call_script_1930 (MONEY_SENT only). Line 1 MUST contain the UTR:
      "UTR <utr>: I want to report a financial cyber fraud. Amount ₹X sent on <date time>
       from <bank, a/c ••••1234> by <rail> to beneficiary a/c <acct>, IFSC <ifsc> / UPI <upi>,
       bank <bank>."
    - bank_email: subject starts with "URGENT: fraud" + UTR (if any); same facts first.
    - ncrp_draft: NcrpField list in this order: Incident date/time, Category ("Online Financial
      Fraud"), Platform/channel, Suspect identifiers (beneficiary account, IFSC, UPI, sender
      email domain, phone), Transaction table (UTR, amount, date, rail), Description.
    - chakshu_note: suspect phone / WhatsApp id if any, else None.
    - evidence_index: one item per case.evidence (analysis_runs as "detector@version").
    - custody_head: custody_rows[-1].row_hash if any.
    - sec63_helper: template text for the company's OWN custodian to sign (we never sign it).
    """
    facts = _transaction_facts(case)
    _check_unlock(case, variant, facts)
    call_script = _call_script_1930(case, facts) if variant == "MONEY_SENT" else None

    # Platform/channel from evidence
    channels = sorted({e.channel.value for e in case.evidence})
    platform_channel = ", ".join(channels) if channels else "Online / Email"

    # Suspect identifiers
    suspect_parts = []
    if facts.beneficiary_account:
        suspect_parts.append(f"Account: {facts.beneficiary_account}")
    if facts.beneficiary_ifsc:
        suspect_parts.append(f"IFSC: {facts.beneficiary_ifsc}")
    if facts.beneficiary_upi:
        suspect_parts.append(f"UPI: {facts.beneficiary_upi}")
    if facts.beneficiary_bank:
        suspect_parts.append(f"Bank: {facts.beneficiary_bank}")
    suspect_identifiers = ", ".join(suspect_parts) if suspect_parts else facts.beneficiary_name

    # Transaction table summary
    txn_table = (
        f"UTR: {facts.utr or 'Pending'} | "
        f"Amount: {format_inr(facts.amount_inr)} | "
        f"Date: {_fmt_when(facts.sent_at, 'N/A')} | "
        f"Rail: {facts.rail}"
    )

    ncrp_draft = [
        NcrpField(label="Incident date/time", value=_fmt_when(facts.sent_at, "N/A")),
        NcrpField(label="Category", value="Online Financial Fraud"),
        NcrpField(label="Platform/channel", value=platform_channel),
        NcrpField(label="Suspect identifiers", value=suspect_identifiers),
        NcrpField(label="Transaction table", value=txn_table),
        NcrpField(
            label="Description",
            value=(
                f"Financial cyber fraud incident under case {case.id}. "
                f"Unauthorized transfer of {format_inr(facts.amount_inr)} to "
                f"{facts.beneficiary_name} via {facts.rail}."
            ),
        ),
    ]

    evidence_index = [
        EvidenceIndexItem(
            evidence_id=e.id,
            filename=e.filename,
            sha256=e.sha256,
            captured_at=e.captured_at,
            channel=e.channel,
            submitted_by=e.submitted_by,
            analysis_runs=[f"{r.detector}@{r.version}" for r in e.analysis_runs],
        )
        for e in case.evidence
    ]

    sec63_helper = (
        f"CERTIFICATE UNDER SECTION 63 OF THE BHARATIYA SAKSHYA ADHINIYAM, 2023\n\n"
        f"Case ID: {case.id}\n"
        f"Generated At: {_fmt_when(now, 'N/A')}\n\n"
        f"I hereby certify that the electronic records and computer outputs associated with "
        f"this incident were produced in the ordinary course of business. The system hashes "
        f"(SHA-256) and chain of custody recorded herein have been preserved securely.\n\n"
        f"Signature of System Custodian: _______________________\n"
        f"Name / Title: _______________________\n"
        f"(To be signed by the person in charge of the device/system; counsel to review)"
    )

    return ReportPack(
        case_id=case.id,
        variant=variant,
        generated_at=now,
        generated_by=generated_by,
        facts=facts,
        call_script_1930=call_script,
        bank_email=_bank_email(case, master, facts, generated_by),
        ncrp_draft=ncrp_draft,
        chakshu_note=None,
        evidence_index=evidence_index,
        custody_head=custody_rows[-1].row_hash if custody_rows else None,
        sec63_helper=sec63_helper,
    )


def render_html(pack: ReportPack) -> str:
    """Printable HTML. html.escape() EVERY value (evidence may contain attacker text).
    The 1930 script (if any) comes first, then bank email, NCRP draft, evidence index."""
    parts = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "<meta charset='utf-8'>",
        f"<title>Report Pack — {html.escape(pack.case_id)}</title>",
        "<style>",
        "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; "
        "margin: 2rem; color: #1e293b; line-height: 1.5; }",
        "h1, h2, h3 { color: #0f172a; margin-top: 0; }",
        ".section { border: 1px solid #cbd5e1; padding: 1.25rem; margin-bottom: 1.5rem; "
        "border-radius: 6px; background: #f8fafc; }",
        "pre { background: #f1f5f9; padding: 1rem; border-radius: 4px; white-space: pre-wrap; "
        "font-family: monospace; font-size: 0.9rem; }",
        "table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }",
        "th, td { border: 1px solid #cbd5e1; padding: 0.6rem; text-align: left; }",
        "th, td { font-size: 0.875rem; }",
        "th { background: #e2e8f0; font-weight: 600; }",
        ".header-meta { font-size: 0.9rem; color: #475569; margin-bottom: 1.5rem; }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>Incident Report Pack: {html.escape(pack.case_id)} ({html.escape(pack.variant)})</h1>",
        "<div class='header-meta'>",
        f"<strong>Generated at:</strong> {html.escape(_fmt_when(pack.generated_at, 'N/A'))} | "
        f"<strong>Generated by:</strong> {html.escape(pack.generated_by)} | "
        f"<strong>Submission:</strong> {html.escape(pack.submission)}",
        "</div>",
    ]

    # 1. 1930 script MUST come first (contains UTR)
    if pack.call_script_1930:
        parts.extend(
            [
                "<div class='section'>",
                "<h2>1930 Helpline Call Script (Spoken Draft)</h2>",
                f"<pre>{html.escape(pack.call_script_1930)}</pre>",
                "</div>",
            ]
        )

    # 2. Bank email draft
    parts.extend(
        [
            "<div class='section'>",
            "<h2>Bank Fraud-Desk Email Draft</h2>",
            f"<p><strong>To:</strong> {html.escape(pack.bank_email.to_hint)}</p>",
            f"<p><strong>Subject:</strong> {html.escape(pack.bank_email.subject)}</p>",
            f"<pre>{html.escape(pack.bank_email.body)}</pre>",
            "</div>",
        ]
    )

    # 3. NCRP draft
    parts.extend(
        [
            "<div class='section'>",
            "<h2>NCRP Complaint Draft</h2>",
            "<table>",
            "<thead><tr><th>Field</th><th>Value</th></tr></thead>",
            "<tbody>",
        ]
    )
    for field in pack.ncrp_draft:
        parts.append(
            f"<tr><td><strong>{html.escape(field.label)}</strong></td>"
            f"<td>{html.escape(field.value)}</td></tr>"
        )
    parts.extend(["</tbody></table></div>"])

    # 4. Evidence index
    parts.extend(
        [
            "<div class='section'>",
            "<h2>Evidence Index</h2>",
            "<table>",
            "<thead><tr><th>Evidence ID</th><th>Filename</th><th>Channel</th>"
            "<th>SHA-256 Hash</th><th>Captured At</th><th>Analysis Runs</th></tr></thead>",
            "<tbody>",
        ]
    )
    for ev in pack.evidence_index:
        runs = ", ".join(ev.analysis_runs) if ev.analysis_runs else "none"
        parts.append(
            f"<tr><td>{html.escape(ev.evidence_id)}</td>"
            f"<td>{html.escape(ev.filename or 'N/A')}</td>"
            f"<td>{html.escape(ev.channel.value)}</td>"
            f"<td><code>{html.escape(ev.sha256)}</code></td>"
            f"<td>{html.escape(_fmt_when(ev.captured_at, 'N/A'))}</td>"
            f"<td>{html.escape(runs)}</td></tr>"
        )
    parts.extend(["</tbody></table>"])
    if pack.custody_head:
        parts.append(
            f"<p style='margin-top:0.75rem'><strong>Custody Chain Head:</strong> "
            f"<code>{html.escape(pack.custody_head)}</code></p>"
        )
    parts.append("</div>")

    # 5. BSA Sec 63 helper
    if pack.sec63_helper:
        parts.extend(
            [
                "<div class='section'>",
                "<h2>BSA Section 63 Certificate Helper</h2>",
                f"<pre>{html.escape(pack.sec63_helper)}</pre>",
                "</div>",
            ]
        )

    parts.append(f"<p><em>{html.escape(pack.disclaimer)}</em></p>")
    parts.append("</body></html>")
    return "\n".join(parts)
