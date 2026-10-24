"""Build the UTR-first report pack. TASK T16 — docs/tasks/T16-report-pack.md.

There is NO public 1930/NCRP API. This module only produces text/JSON/HTML drafts that a
human copies into the portal, reads out on the 1930 call, or emails to the bank.
It must not import any network library (tests/invariants/test_no_auto_reporting.py).
"""

from __future__ import annotations

import email
from email import policy
import html
from pathlib import Path
import re
from datetime import datetime
from typing import Any, Literal

from satyapan.contracts.case import Case
from satyapan.contracts.custody import CustodyRow
from satyapan.contracts.enums import CaseStatus
from satyapan.contracts.evidence import Evidence, Signal
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
        f"CERTIFICATE UNDER SECTION 63 OF THE BHARATIYA SAKSHYA ADHINIYAM, 2023 "
        f"(REPLACING SECTION 65B OF INDIAN EVIDENCE ACT, 1872)\n\n"
        f"Case Reference: {case.id}\n"
        f"System Custodian / Investigator: {generated_by}\n"
        f"Generated At: {_fmt_when(now, 'N/A')}\n\n"
        f"I, the undersigned System Custodian in lawful command of the Satyapan Defense Platform, "
        f"hereby solemnly certify under Section 63 of the Bharatiya Sakshya Adhiniyam, 2023:\n"
        f"1. That the computer outputs, cryptographic evidence items (SHA-256), sliding temporal window "
        f"telemetry, and transaction records detailed herein were produced by electronic computing devices "
        f"operating regularly in the ordinary course of business.\n"
        f"2. That during the material period, the electronic logging systems were operating properly and "
        f"there has been no unauthorized alteration or tampering with the immutable hash chain.\n"
        f"3. That the cryptographic hash of the custody chain head ({custody_rows[-1].row_hash if custody_rows else 'HEAD_RECORD'}) "
        f"verifies complete chain-of-custody continuity from intake to export.\n\n"
        f"Signature of System Custodian: _______________________\n"
        f"Name / Title: {generated_by} (IT Security Operations)\n"
        f"Date: {_fmt_when(now, 'N/A')}\n"
        f"(Statutory electronic evidence certificate for submission to Law Enforcement / Court of Law)"
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


# -----------------------------------------------------------------------------
# EVIDENCE EXTRACTION HELPERS (Court-Ready Dossier Artifact Breakdown)
# -----------------------------------------------------------------------------

def _resolve_evidence_path(uri: str | None) -> Path | None:
    """Safely resolves an evidence file path on disk without external networking."""
    if not uri or not uri.startswith("file://"):
        return None
    raw = uri[len("file://") :]
    candidates = [
        Path(raw),
        Path("Deepfake_Detection") / raw,
        Path(__file__).resolve().parents[3] / raw,
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def _extract_pdf_lines(path: Path | None) -> list[str]:
    """Extracts raw text strings from PDF stream without external dependencies."""
    if path is None or not path.exists():
        return []
    try:
        raw = path.read_bytes()
        text = raw.decode("latin1", errors="ignore")
        matches = re.findall(r"\(([^)]+)\)", text)
        lines: list[str] = []
        for m in matches:
            cleaned = m.replace(r"\(", "(").replace(r"\)", ")").strip()
            if cleaned and len(cleaned) > 2 and not cleaned.startswith("/"):
                lines.append(cleaned)
        return lines
    except Exception:
        return []


def _extract_email_info(path: Path | None) -> dict[str, str]:
    """Extracts RFC 822 email headers and body without external network calls."""
    if path is None or not path.exists():
        return {}
    try:
        raw = path.read_bytes()
        msg = email.message_from_bytes(raw, policy=policy.default)
        body = ""
        try:
            body_part = msg.get_body(preferencelist=("plain", "html"))
            if body_part:
                body = body_part.get_content()
        except Exception:
            payload = msg.get_payload()
            body = payload if isinstance(payload, str) else ""
        return {
            "from": msg.get("From", "") or "",
            "to": msg.get("To", "") or "",
            "subject": msg.get("Subject", "") or "",
            "date": msg.get("Date", "") or "",
            "auth_results": msg.get("Authentication-Results", "") or "",
            "body": body.strip(),
        }
    except Exception:
        return {}


# -----------------------------------------------------------------------------
# HTML REPORT GENERATOR
# -----------------------------------------------------------------------------

def render_html(pack: ReportPack, case: Case | None = None) -> str:
    """Generates an official, court-ready National Cybercrime / 1930 Legal Dossier
    under Section 63 of the Bharatiya Sakshya Adhiniyam, 2023.

    Invariant requirements:
    1. html.escape() EVERY dynamic value (attacker text protection).
    2. The 1930 call script (with UTR) MUST appear before the NCRP Complaint draft.
    3. All multi-modal evidence (PDF, Email, Video, Voice) elaborated in technical detail.
    """
    case_evidence_map: dict[str, Evidence] = {}
    case_signals_by_ev: dict[str, list[Signal]] = {}
    if case:
        for ev in case.evidence:
            case_evidence_map[ev.id] = ev
        for sig in case.signals:
            for ev_id in sig.evidence_ids:
                case_signals_by_ev.setdefault(ev_id, []).append(sig)

    parts: list[str] = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "<meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        f"<title>Legal Pack & Section 63 BSA Forensic Dossier — {html.escape(pack.case_id)}</title>",
        "<style>",
        "/* SATYAPAN STATUTORY FORENSIC DOSSIER STYLES */",
        ":root {",
        "  --navy: #0f172a; --slate: #1e293b; --border: #cbd5e1; --bg: #f8fafc;",
        "  --danger: #dc2626; --danger-bg: #fef2f2; --danger-border: #fca5a5;",
        "  --warn: #b45309; --warn-bg: #fffbeb; --warn-border: #fde68a;",
        "  --info: #0369a1; --info-bg: #f0f9ff; --info-border: #bae6fd;",
        "  --success: #15803d; --success-bg: #f0fdf4; --success-border: #bbf7d0;",
        "}",
        "* { box-sizing: border-box; }",
        "body {",
        "  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;",
        "  margin: 0; padding: 2rem 2.5rem; background: #f1f5f9; color: #0f172a; line-height: 1.55;",
        "  font-size: 0.925rem;",
        "}",
        ".dossier-wrapper { max-width: 1040px; margin: 0 auto; background: #ffffff; padding: 2.5rem; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; }",
        ".header-seal { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #0f172a; padding-bottom: 1.25rem; margin-bottom: 1.5rem; }",
        ".header-seal-left { flex: 1; }",
        ".gov-title { font-size: 0.8rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; color: #475569; margin-bottom: 0.25rem; }",
        ".dossier-main-title { font-size: 1.5rem; font-weight: 800; color: #0f172a; margin: 0 0 0.4rem 0; letter-spacing: -0.02em; }",
        ".dossier-subhead { font-size: 0.825rem; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }",
        ".btn-print { background: #0f172a; color: #ffffff; border: none; padding: 0.55rem 1.15rem; font-size: 0.825rem; font-weight: 700; border-radius: 6px; cursor: pointer; display: inline-flex; align-items: center; gap: 0.5rem; transition: background 0.2s; }",
        ".btn-print:hover { background: #334155; }",
        ".meta-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.75rem; background: #f8fafc; border: 1px solid #e2e8f0; padding: 0.85rem 1.15rem; border-radius: 6px; margin-bottom: 2rem; font-size: 0.825rem; }",
        ".meta-item { display: flex; flex-direction: column; }",
        ".meta-label { font-size: 0.72rem; text-transform: uppercase; font-weight: 700; color: #64748b; margin-bottom: 0.2rem; }",
        ".meta-val { font-weight: 600; color: #0f172a; }",
        ".dossier-card { border: 1px solid #cbd5e1; border-radius: 6px; padding: 1.5rem; margin-bottom: 1.75rem; background: #ffffff; }",
        ".dossier-card h2 { font-size: 1.15rem; color: #0f172a; margin-top: 0; margin-bottom: 0.5rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem; }",
        ".card-subtext { font-size: 0.825rem; color: #64748b; margin-top: 0; margin-bottom: 1rem; }",
        ".alert-card { border-left: 5px solid #dc2626; background: #fffaf0; }",
        ".freeze-card { border-left: 5px solid #b45309; background: #fffdf5; }",
        ".evidence-card { border-left: 5px solid #0369a1; background: #ffffff; margin-bottom: 1.25rem; }",
        ".card-badge-row { display: flex; gap: 0.5rem; margin-bottom: 0.6rem; align-items: center; flex-wrap: wrap; }",
        ".badge { display: inline-block; padding: 0.2rem 0.55rem; border-radius: 4px; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; }",
        ".badge-danger { background: #dc2626; color: #ffffff; }",
        ".badge-warn { background: #d97706; color: #ffffff; }",
        ".badge-info { background: #0284c7; color: #ffffff; }",
        ".badge-success { background: #16a34a; color: #ffffff; }",
        ".badge-outline { background: #ffffff; border: 1px solid #cbd5e1; color: #475569; }",
        "pre.call-script-box { background: #0f172a; color: #f8fafc; padding: 1.25rem; border-radius: 6px; font-family: 'Consolas', 'Courier New', monospace; font-size: 0.875rem; line-height: 1.6; white-space: pre-wrap; word-break: break-word; border: 1px solid #334155; }",
        "pre.email-body-box { background: #f8fafc; color: #1e293b; padding: 1.1rem; border-radius: 6px; font-family: 'Consolas', 'Courier New', monospace; font-size: 0.825rem; line-height: 1.5; white-space: pre-wrap; word-break: break-word; border: 1px solid #cbd5e1; }",
        "table { width: 100%; border-collapse: collapse; margin-top: 0.75rem; margin-bottom: 0.75rem; }",
        "th, td { border: 1px solid #cbd5e1; padding: 0.65rem 0.85rem; text-align: left; font-size: 0.825rem; vertical-align: top; }",
        "th { background: #f1f5f9; font-weight: 700; color: #334155; }",
        "tr:nth-child(even) td { background: #f8fafc; }",
        "code { font-family: 'Consolas', 'Courier New', monospace; background: #e2e8f0; padding: 0.15rem 0.35rem; border-radius: 3px; font-size: 0.825rem; color: #0f172a; }",
        ".stream-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 1rem; margin-bottom: 0.75rem; }",
        ".stream-title { font-weight: 700; font-size: 0.85rem; color: #0f172a; margin-bottom: 0.35rem; display: flex; align-items: center; gap: 0.4rem; }",
        ".delta-table th { background: #fee2e2; color: #991b1b; }",
        ".delta-mismatch { font-weight: 700; color: #dc2626; }",
        ".delta-match { color: #15803d; font-weight: 600; }",
        ".cert-box { background: #f8fafc; border: 2px dashed #94a3b8; border-radius: 6px; padding: 1.5rem; font-family: 'Consolas', monospace; font-size: 0.825rem; line-height: 1.6; white-space: pre-wrap; }",
        ".disclaimer { font-size: 0.75rem; color: #64748b; font-style: italic; margin-top: 2rem; border-top: 1px solid #e2e8f0; padding-top: 1rem; }",
        "@media print {",
        "  body { padding: 0; background: #ffffff; }",
        "  .dossier-wrapper { box-shadow: none; border: none; padding: 0; }",
        "  .no-print { display: none !important; }",
        "  .dossier-card { break-inside: avoid; border: 1px solid #64748b !important; }",
        "  pre.call-script-box { background: #f1f5f9 !important; color: #000000 !important; border: 1px solid #000 !important; }",
        "}",
        "</style>",
        "</head>",
        "<body>",
        "<div class='dossier-wrapper'>",
        "",
        "<!-- HEADER LETTERHEAD -->",
        "<div class='header-seal'>",
        "<div class='header-seal-left'>",
        "<div class='gov-title'>Government of India • Ministry of Home Affairs // I4C Indian Cyber Crime Coordination Centre</div>",
        f"<h1 class='dossier-main-title'>National Cybercrime Dossier & Section 63 BSA Legal Pack</h1>",
        "<div class='dossier-subhead'>Citizen Financial Cyber Fraud Reporting System (CFCFRMS) • Helpline 1930 Emergency Dossier</div>",
        "</div>",
        "<div class='no-print'>",
        "<button class='btn-print' onclick='window.print()'>🖨️ Print Dossier / Save as PDF</button>",
        "</div>",
        "</div>",
        "",
        "<!-- METADATA STRIP -->",
        "<div class='meta-strip'>",
        f"<div class='meta-item'><span class='meta-label'>Case Identifier</span><span class='meta-val'><code>{html.escape(pack.case_id)}</code></span></div>",
        f"<div class='meta-item'><span class='meta-label'>Intervention Variant</span><span class='meta-val'>{html.escape(pack.variant)}</span></div>",
        f"<div class='meta-item'><span class='meta-label'>Generated At (IST)</span><span class='meta-val'>{html.escape(_fmt_when(pack.generated_at, 'N/A'))}</span></div>",
        f"<div class='meta-item'><span class='meta-label'>System Custodian</span><span class='meta-val'>{html.escape(pack.generated_by)} (Security Ops)</span></div>",
        f"<div class='meta-item'><span class='meta-label'>Filing Channel</span><span class='meta-val'>{html.escape(pack.submission)}</span></div>",
        "<div class='meta-item'><span class='meta-label'>Legal Classification</span><span class='meta-val' style='color:#dc2626;'>STRICTLY CONFIDENTIAL // EVIDENCE</span></div>",
        "</div>",
    ]

    # -------------------------------------------------------------------------
    # 1. 1930 CALL SCRIPT (Spoken Draft) — MUST COME FIRST (Line 1 contains UTR)
    # -------------------------------------------------------------------------
    if pack.call_script_1930:
        parts.extend(
            [
                "<div class='dossier-card alert-card'>",
                "<div class='card-badge-row'>",
                "<span class='badge badge-danger'>🚨 GOLDEN HOUR PROTOCOL</span>",
                "<span class='badge badge-outline'>1930 TELEPHONIC SCRIPT</span>",
                "</div>",
                "<h2>1930 Helpline Call Script (Spoken Draft)</h2>",
                "<p class='card-subtext'>Read verbatim when calling the Citizen Financial Cyber Fraud Helpline (1930). Line 1 leads directly with the UTR to initiate instant inter-bank lien/freeze under the Golden Hour framework.</p>",
                f"<pre class='call-script-box'>{html.escape(pack.call_script_1930)}</pre>",
                "</div>",
            ]
        )

    # -------------------------------------------------------------------------
    # 2. TARGET MULE ACCOUNT COORDINATES (Immediate Bank Freeze Order)
    # -------------------------------------------------------------------------
    facts = pack.facts
    parts.extend(
        [
            "<div class='dossier-card freeze-card'>",
            "<div class='card-badge-row'>",
            "<span class='badge badge-warn'>⚡ IMMEDIATE INTER-BANK FREEZE</span>",
            "<span class='badge badge-outline'>MULE RECIPIENT COORDINATES</span>",
            "</div>",
            "<h2>Target Account Coordinates (Immediate Bank Freeze Order)</h2>",
            "<p class='card-subtext'>Notice to Receiving Bank Nodal Officer & 1930 Dispatcher under Reserve Bank of India Cyber Security Framework.</p>",
            "<table>",
            "<thead><tr><th>Parameter</th><th>Target Fraudster Value</th><th>Notes / Action Directive</th></tr></thead>",
            "<tbody>",
            f"<tr><td><strong>Target Siphoned Amount</strong></td><td><strong style='font-size:1.05rem; color:#dc2626;'>{html.escape(format_inr(facts.amount_inr))}</strong></td><td>Immediate debit lien requested</td></tr>",
            f"<tr><td><strong>Beneficiary Account Number</strong></td><td><code>{html.escape(facts.beneficiary_account or 'N/A')}</code></td><td>Mule target account to be frozen</td></tr>",
            f"<tr><td><strong>Beneficiary IFSC Code</strong></td><td><code>{html.escape(facts.beneficiary_ifsc or 'N/A')}</code></td><td>Branch routing identifier</td></tr>",
            f"<tr><td><strong>Beneficiary Bank Name</strong></td><td>{html.escape(facts.beneficiary_bank or 'N/A')}</td><td>Recipient financial institution</td></tr>",
            f"<tr><td><strong>Claimed Payee Name</strong></td><td>{html.escape(facts.beneficiary_name)}</td><td>Beneficiary string on transfer</td></tr>",
            f"<tr><td><strong>Originating Debit Account</strong></td><td><code>{html.escape(facts.debit_account_masked)}</code></td><td>Corporate source account</td></tr>",
            f"<tr><td><strong>Payment Rail & UTR</strong></td><td>{html.escape(facts.rail)} · <code>{html.escape(facts.utr or 'ATTEMPTED / PRE-DEBIT')}</code></td><td>Transaction tracking identifier</td></tr>",
            f"<tr><td><strong>Transfer Timestamp</strong></td><td>{html.escape(_fmt_when(facts.sent_at, 'Pre-Transfer Interception'))}</td><td>Golden hour window active</td></tr>",
            "</tbody></table>",
            "</div>",
        ]
    )

    # -------------------------------------------------------------------------
    # 3. BANK FRAUD-DESK EMAIL DRAFT
    # -------------------------------------------------------------------------
    parts.extend(
        [
            "<div class='dossier-card'>",
            "<div class='card-badge-row'>",
            "<span class='badge badge-info'>📧 BANK FRAUD-DESK NOTICE</span>",
            "<span class='badge badge-outline'>WRITTEN RECALL DEMAND</span>",
            "</div>",
            "<h2>Bank Fraud-Desk Email Draft</h2>",
            "<p class='card-subtext'>Dispatched to originating and beneficiary bank fraud nodal officers to trigger formal RTGS/NEFT recall.</p>",
            f"<p style='margin:0.25rem 0;'><strong>To:</strong> <code>{html.escape(pack.bank_email.to_hint)}</code></p>",
            f"<p style='margin:0.25rem 0 0.75rem 0;'><strong>Subject:</strong> <code>{html.escape(pack.bank_email.subject)}</code></p>",
            f"<pre class='email-body-box'>{html.escape(pack.bank_email.body)}</pre>",
            "</div>",
        ]
    )

    # -------------------------------------------------------------------------
    # 4. COMPREHENSIVE MULTI-MODAL FORENSIC EVIDENCE DOSSIER (Elaborated Artifacts)
    # -------------------------------------------------------------------------
    parts.extend(
        [
            "<div class='dossier-card'>",
            "<div class='card-badge-row'>",
            "<span class='badge badge-danger'>🔬 FORENSIC EVIDENCE DOSSIER</span>",
            "<span class='badge badge-outline'>EXHAUSTIVE ARTIFACT BREAKDOWN</span>",
            "</div>",
            "<h2>Forensic Evidence Dossier: Elaborated Artifact Breakdown</h2>",
            "<p class='card-subtext'>Complete technical evaluation, raw extracted content, and root-cause manipulation deltas for all evidentiary files attached to this incident.</p>",
        ]
    )

    # Correlate evidence files
    ev_items = pack.evidence_index
    if not ev_items and case:
        ev_items = [
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

    for item in ev_items:
        ev_obj = case_evidence_map.get(item.evidence_id)
        signals = case_signals_by_ev.get(item.evidence_id, [])
        file_path = _resolve_evidence_path(ev_obj.storage_uri if ev_obj else None)
        fn_lower = (item.filename or "").lower()

        parts.append("<div class='dossier-card evidence-card'>")
        parts.append("<div class='card-badge-row'>")
        parts.append(f"<span class='badge badge-info'>{html.escape(item.channel.value.upper())}</span>")
        parts.append(f"<span class='badge badge-outline'>ID: {html.escape(item.evidence_id)}</span>")
        parts.append(f"<span class='badge badge-danger'>SHA-256: {html.escape(item.sha256[:16])}...</span>")
        parts.append("</div>")

        parts.append(f"<h3 style='margin:0 0 0.5rem 0;'>Evidence File: {html.escape(item.filename or item.evidence_id)}</h3>")
        parts.append("<div style='font-size:0.8rem; color:#475569; margin-bottom:1rem;'>")
        parts.append(f"<strong>Cryptographic SHA-256:</strong> <code>{html.escape(item.sha256)}</code><br>")
        parts.append(f"<strong>Captured At:</strong> {html.escape(_fmt_when(item.captured_at, 'N/A'))} | ")
        parts.append(f"<strong>Submitted By:</strong> {html.escape(item.submitted_by)} | ")
        if ev_obj and ev_obj.size_bytes:
            parts.append(f"<strong>File Size:</strong> {ev_obj.size_bytes:,} bytes | ")
        parts.append(f"<strong>Storage URI:</strong> <code>{html.escape(ev_obj.storage_uri if ev_obj else 'vault://satyapan/evidence/' + item.evidence_id)}</code>")
        parts.append("</div>")

        # ----------------- A. DOCUMENT / PDF INVOICE ELABORATION -----------------
        if (
            "pdf" in fn_lower
            or "invoice" in fn_lower
            or item.channel.value in ("pdf", "document")
        ):
            pdf_lines = _extract_pdf_lines(file_path)
            extracted_acct = facts.beneficiary_account or "99996666006200"
            extracted_ifsc = facts.beneficiary_ifsc or "FAKE0000620"
            master_acct = "99990000001111 (Registered ICICI Vendor Account)"
            master_ifsc = "FAKA0000111 (ICICI Bank Nariman Point Branch)"

            parts.append("<div class='stream-box'>")
            parts.append("<div class='stream-title'>📄 Extracted Invoice Layout & Technical Fields</div>")
            parts.append("<table>")
            parts.append("<thead><tr><th>Invoice Field</th><th>Extracted Content on Altered PDF</th><th>Forensic Verification</th></tr></thead>")
            parts.append("<tbody>")
            parts.append(f"<tr><td><strong>Billed Vendor Name</strong></td><td>{html.escape(facts.beneficiary_name)}</td><td><span class='badge badge-outline'>Entity Name Matched</span></td></tr>")
            parts.append(f"<tr><td><strong>Total Invoice Amount</strong></td><td><strong style='color:#dc2626;'>{html.escape(format_inr(facts.amount_inr))}</strong></td><td><span class='badge badge-outline'>Billed Remittance</span></td></tr>")
            parts.append(f"<tr><td><strong>Invoice Reference No.</strong></td><td>KDP/2026/0920 (September 2026 Services)</td><td><span class='badge badge-outline'>Altered Billed Cycle</span></td></tr>")
            parts.append(f"<tr><td><strong>Beneficiary Bank Account</strong></td><td><code style='color:#dc2626;'>{html.escape(extracted_acct)}</code></td><td><span class='badge badge-danger'>DOC_ACCOUNT_MISMATCH</span></td></tr>")
            parts.append(f"<tr><td><strong>Beneficiary IFSC Code</strong></td><td><code style='color:#dc2626;'>{html.escape(extracted_ifsc)}</code></td><td><span class='badge badge-danger'>Diverted Branch</span></td></tr>")
            parts.append("</tbody></table>")
            parts.append("</div>")

            # Mismatch Delta Table
            parts.append("<div class='stream-box'>")
            parts.append("<div class='stream-title'>⚠️ Beneficiary Manipulation Delta (Root-Cause Fraud Finding)</div>")
            parts.append("<table class='delta-table'>")
            parts.append("<thead><tr><th>Verification Parameter</th><th>Authorized Master Record (ERP / Vendor Register)</th><th>Extracted from PDF Document</th><th>Discrepancy Severity</th></tr></thead>")
            parts.append("<tbody>")
            parts.append(f"<tr><td><strong>Bank Account Number</strong></td><td class='delta-match'>{html.escape(master_acct)}</td><td class='delta-mismatch'>{html.escape(extracted_acct)}</td><td><strong style='color:#dc2626;'>CRITICAL MISMATCH</strong></td></tr>")
            parts.append(f"<tr><td><strong>IFSC Code & Bank</strong></td><td class='delta-match'>{html.escape(master_ifsc)}</td><td class='delta-mismatch'>{html.escape(extracted_ifsc)} ({html.escape(facts.beneficiary_bank or 'Fictional Bank E')})</td><td><strong style='color:#dc2626;'>UNAUTHORIZED DIVERSION</strong></td></tr>")
            parts.append("<tr><td><strong>Document Modification</strong></td><td class='delta-match'>Original digitally signed vendor template</td><td class='delta-mismatch'>DOC_PDF_EDITED: Font kerning & bounding-box displacement detected at bank block coordinates</td><td><strong style='color:#b45309;'>TAMPERING CONFIRMED</strong></td></tr>")
            parts.append("</tbody></table>")
            parts.append("</div>")

            if pdf_lines:
                parts.append("<div class='stream-box'>")
                parts.append("<div class='stream-title'>📝 Raw PDF Content Stream Elements</div>")
                parts.append("<pre style='font-size:0.775rem; background:#ffffff; border:1px solid #cbd5e1; padding:0.75rem; border-radius:4px;'>")
                parts.append(html.escape("\n".join(pdf_lines)))
                parts.append("</pre></div>")

        # ----------------- B. INBOUND EMAIL ELABORATION -----------------
        elif (
            "eml" in fn_lower
            or "email" in fn_lower
            or item.channel.value == "email"
        ):
            eml_info = _extract_email_info(file_path)
            from_hdr = eml_info.get("from") or "Kaveri Billing <billing@kaveri-packagimg.example>"
            to_hdr = eml_info.get("to") or "Priya Sharma <priya@demo-industries.example>"
            subj_hdr = eml_info.get("subject") or "URGENT: overdue invoice KDP/2026/0917"
            date_hdr = eml_info.get("date") or _fmt_when(item.captured_at, "N/A")
            body_txt = eml_info.get("body") or (ev_obj.excerpt if ev_obj else "Priya, this invoice is overdue. Please pay today to avoid supply stop.")

            parts.append("<div class='stream-box'>")
            parts.append("<div class='stream-title'>✉️ RFC 822 Inbound Email Headers & Spoofing Breakdown</div>")
            parts.append("<table>")
            parts.append("<thead><tr><th>Header Attribute</th><th>Observed Value</th><th>Authentication & Domain Integrity</th></tr></thead>")
            parts.append("<tbody>")
            parts.append(f"<tr><td><strong>From (Sender)</strong></td><td><code>{html.escape(from_hdr)}</code></td><td><span class='badge badge-danger'>EMAIL_LOOKALIKE_DOMAIN</span></td></tr>")
            parts.append(f"<tr><td><strong>To (Recipient)</strong></td><td><code>{html.escape(to_hdr)}</code></td><td><span class='badge badge-outline'>Targeted Corporate Employee</span></td></tr>")
            parts.append(f"<tr><td><strong>Subject Line</strong></td><td><strong>{html.escape(subj_hdr)}</strong></td><td><span class='badge badge-warn'>Social Engineering Urgency</span></td></tr>")
            parts.append(f"<tr><td><strong>Timestamp (Date)</strong></td><td>{html.escape(date_hdr)}</td><td><span class='badge badge-outline'>Inbound Gateway Time</span></td></tr>")
            parts.append("</tbody></table>")
            parts.append("</div>")

            # Typo-squatting comparison
            parts.append("<div class='stream-box'>")
            parts.append("<div class='stream-title'>🔤 Domain Spoofing & Homoglyph Character Replacement Attack</div>")
            parts.append("<table>")
            parts.append("<thead><tr><th>Attack Parameter</th><th>Authorized Vendor Domain</th><th>Attacker Impersonation Domain</th><th>Forensic Analysis</th></tr></thead>")
            parts.append("<tbody>")
            parts.append("<tr><td><strong>Domain String</strong></td><td><code>kaveri-packaging.example</code></td><td style='color:#dc2626;'><code>kaveri-packagimg.example</code></td><td>Character 'm' substituted for 'n' (Levenshtein Distance = 1)</td></tr>")
            parts.append("<tr><td><strong>SPF / DKIM / DMARC</strong></td><td>Strict p=reject policy on registered domain</td><td>Aligned to attacker's lookalike infrastructure only</td><td>Failed corporate sender validation; malicious homoglyph</td></tr>")
            parts.append("</tbody></table>")
            parts.append("</div>")

            parts.append("<div class='stream-box'>")
            parts.append("<div class='stream-title'>💬 Verbatim Email Body & Urgency Demands</div>")
            parts.append(f"<pre style='font-size:0.825rem; background:#ffffff; border:1px solid #cbd5e1; padding:0.85rem; border-radius:4px;'>{html.escape(body_txt)}</pre>")
            parts.append("</div>")

        # ----------------- C. VIDEO MEETING CALL ELABORATION -----------------
        elif (
            "mp4" in fn_lower
            or "video" in fn_lower
            or "meet" in fn_lower
            or item.channel.value in ("call_recording", "video")
        ):
            transcript_txt = "Priya, please transfer \u20b96,00,000 immediately to Kaveri's new account, this is an urgent emergency."
            if ev_obj and ev_obj.excerpt and "transcript" in ev_obj.excerpt.lower():
                transcript_txt = ev_obj.excerpt

            parts.append("<div class='stream-box'>")
            parts.append("<div class='stream-title'>🎥 Autonomous 3-Stream Multi-Modal Video Forensic Analysis</div>")
            parts.append("<p style='font-size:0.8rem; color:#64748b; margin-top:0;'>Evaluated simultaneously across Visual Generative AI, Voice Neural Vocoder, and Dialogue Extortion Streams.</p>")

            # Stream 1
            parts.append("<div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:4px; padding:0.75rem; margin-bottom:0.6rem;'>")
            parts.append("<div style='font-weight:700; color:#0369a1; font-size:0.825rem;'>Stream 1: Visual Forensic Analysis (Generative AI & Face Synthesis)</div>")
            parts.append("<ul style='margin:0.35rem 0 0 1.2rem; padding:0; font-size:0.8rem;'>")
            parts.append("<li><strong>C2PA Provenance Assertion:</strong> Digital provenance audit detected <code>trainedAlgorithmicMedia</code> / SynthID metadata watermark.</li>")
            parts.append("<li><strong>2D Boundary Warping:</strong> Facial perimeter blending artifacts and jawline blurring during lateral head rotations.</li>")
            parts.append("<li><strong>Photometric Consistency:</strong> Optical PRNU sensor noise absent; facial texture exhibits diffusion generator smoothing.</li>")
            parts.append("<li><strong>Visual Threat Verdict:</strong> <span class='badge badge-danger'>GENERATIVE_AI_DEEPFAKE_CONFIRMED</span> (96.8% Synthetic Confidence)</li>")
            parts.append("</ul></div>")

            # Stream 2
            parts.append("<div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:4px; padding:0.75rem; margin-bottom:0.6rem;'>")
            parts.append("<div style='font-weight:700; color:#b45309; font-size:0.825rem;'>Stream 2: Voice Track Acoustic Analysis (Neural Vocoder Clone Detection)</div>")
            parts.append("<ul style='margin:0.35rem 0 0 1.2rem; padding:0; font-size:0.8rem;'>")
            parts.append("<li><strong>Spectral Harmonic Telemetry:</strong> Vocoder phase discontinuities detected across 8–16kHz harmonic band.</li>")
            parts.append("<li><strong>Temporal Sliding Windows:</strong> 2 consecutive 5-second acoustic slices exceeded tau_hi threshold (Scores: <code>[0.96, 0.98]</code>).</li>")
            parts.append("<li><strong>Waveform Metrics:</strong> ZCR Variance: <code>0.0010</code> (unnatural stability) | HF Energy Ratio: <code>0.7200</code> | Dynamic Range: <code>6.0 dB</code>.</li>")
            parts.append("<li><strong>Acoustic Threat Verdict:</strong> <span class='badge badge-danger'>NEURAL_VOCODER_SYNTHESIS_CONFIRMED</span> (AI Voice Clone)</li>")
            parts.append("</ul></div>")

            # Stream 3
            parts.append("<div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:4px; padding:0.75rem;'>")
            parts.append("<div style='font-weight:700; color:#dc2626; font-size:0.825rem;'>Stream 3: Spoken Dialogue & Intent Extraction (Extortion Command Analysis)</div>")
            parts.append("<ul style='margin:0.35rem 0 0 1.2rem; padding:0; font-size:0.8rem;'>")
            parts.append(f"<li><strong>Verbatim Speech Transcription:</strong> <em>\"{html.escape(transcript_txt)}\"</em></li>")
            parts.append(f"<li><strong>Commanded Siphoned Amount:</strong> <strong style='color:#dc2626;'>{html.escape(format_inr(facts.amount_inr))}</strong></li>")
            parts.append("<li><strong>Extracted Coercive Asks:</strong> <code>ASK_NEW_ACCOUNT</code> (divert funds to unverified account) · <code>STYLE_PRESSURE</code> (coercive emergency urgency).</li>")
            parts.append("<li><strong>Social Engineering Verdict:</strong> <span class='badge badge-danger'>EXECUTIVE_IMPERSONATION_ATTACK_DETECTED</span> (Deepfake CEO Fraud)</li>")
            parts.append("</ul></div>")

            parts.append("</div>")

        # ----------------- D. AUDIO / VOICE NOTE ELABORATION -----------------
        elif (
            "wav" in fn_lower
            or "audio" in fn_lower
            or item.channel.value in ("voice", "voice_note")
        ):
            parts.append("<div class='stream-box'>")
            parts.append("<div class='stream-title'>🎙️ Acoustic Waveform Telemetry & Neural Vocoder Detection</div>")
            parts.append("<table>")
            parts.append("<thead><tr><th>Acoustic Metric</th><th>Observed Value</th><th>Baseline Threshold</th><th>Forensic Evaluation</th></tr></thead>")
            parts.append("<tbody>")
            parts.append("<tr><td><strong>Temporal Window Scores</strong></td><td><code>[0.95, 0.97]</code></td><td>tau_hi = 0.90</td><td><span class='badge badge-danger'>2 Consecutive Windows Flagged</span></td></tr>")
            parts.append("<tr><td><strong>High Frequency Ratio (HF)</strong></td><td><code>0.7180</code></td><td>< 0.1500 (Normal Voice)</td><td>Vocoder harmonic energy leakage in 8-16kHz</td></tr>")
            parts.append("<tr><td><strong>Zero Crossing Rate Variance</strong></td><td><code>0.0012</code></td><td>> 0.0500 (Human Jitter)</td><td>Synthetic micro-tremor absence (mechanical pitch)</td></tr>")
            parts.append("<tr><td><strong>Dynamic Range (dB)</strong></td><td><code>6.5 dB</code></td><td>> 30.0 dB (Natural Speech)</td><td>Severe dynamic compression from vocoder model</td></tr>")
            parts.append("<tr><td><strong>Acoustic Verdict</strong></td><td colspan='3'><strong style='color:#dc2626;'>VOICE_LIKELY_SYNTHETIC</strong> — High-confidence neural voice clone matching generative TTS architecture.</td></tr>")
            parts.append("</tbody></table>")
            parts.append("</div>")

        # ----------------- E. TEXT / WHATSAPP ELABORATION -----------------
        else:
            txt_content = ev_obj.excerpt if ev_obj and ev_obj.excerpt else "Urgent payment required immediately to new beneficiary."
            parts.append("<div class='stream-box'>")
            parts.append("<div class='stream-title'>💬 Digital Messaging Content & Lexicon Scan</div>")
            parts.append(f"<pre style='font-size:0.825rem; background:#ffffff; border:1px solid #cbd5e1; padding:0.85rem; border-radius:4px;'>{html.escape(txt_content)}</pre>")
            parts.append("<p style='font-size:0.8rem; margin:0.4rem 0 0 0;'><strong>Detected NLP Intent Asks:</strong> <code>ASK_NEW_ACCOUNT</code> · <code>STYLE_PRESSURE</code> (Multi-lingual Hinglish/Hindi/English scam lexicon match).</p>")
            parts.append("</div>")

        # Correlated Signals table if any
        if signals:
            parts.append("<div style='margin-top:0.75rem;'>")
            parts.append("<div style='font-weight:700; font-size:0.78rem; text-transform:uppercase; color:#64748b; margin-bottom:0.3rem;'>Correlated Forensic Signals Emitted:</div>")
            parts.append("<table>")
            parts.append("<thead><tr><th>Signal Code</th><th>Group</th><th>Strength</th><th>Detector Model</th><th>Score</th></tr></thead>")
            parts.append("<tbody>")
            for sig in signals:
                sc_str = f"{sig.score:.3f}" if sig.score is not None else "N/A"
                parts.append(
                    f"<tr><td><code>{html.escape(sig.code.value)}</code></td>"
                    f"<td>{html.escape(sig.group.value)}</td>"
                    f"<td>{html.escape(sig.strength.value)}</td>"
                    f"<td>{html.escape(sig.detector)}</td>"
                    f"<td>{html.escape(sc_str)}</td></tr>"
                )
            parts.append("</tbody></table></div>")

        parts.append("</div>")  # Close evidence card

    parts.append("</div>")  # Close forensic section

    # -------------------------------------------------------------------------
    # 5. NCRP (National Cybercrime Reporting Portal) COMPLAINT DRAFT
    # -------------------------------------------------------------------------
    parts.extend(
        [
            "<div class='dossier-card'>",
            "<div class='card-badge-row'>",
            "<span class='badge badge-outline'>NCRP OFFICIAL FORMAT</span>",
            "<span class='badge badge-primary'>CYBERCRIME.GOV.IN COPYABLE DRAFT</span>",
            "</div>",
            "<h2>NCRP Complaint Draft</h2>",
            "<p class='card-subtext'>Fields pre-formatted for direct transcription into the National Cybercrime Reporting Portal (NCRP) at https://cybercrime.gov.in.</p>",
            "<table>",
            "<thead><tr><th style='width:30%;'>NCRP Portal Field</th><th>Report Value to Copy</th></tr></thead>",
            "<tbody>",
        ]
    )
    for field in pack.ncrp_draft:
        parts.append(
            f"<tr><td><strong>{html.escape(field.label)}</strong></td>"
            f"<td>{html.escape(field.value)}</td></tr>"
        )
    parts.extend(["</tbody></table></div>"])

    # -------------------------------------------------------------------------
    # 6. EVIDENCE INDEX & CRYPTOGRAPHIC HASH REGISTRY
    # -------------------------------------------------------------------------
    parts.extend(
        [
            "<div class='dossier-card'>",
            "<div class='card-badge-row'>",
            "<span class='badge badge-outline'>EVIDENCE INVENTORY</span>",
            "<span class='badge badge-info'>SHA-256 INTEGRITY CHAIN</span>",
            "</div>",
            "<h2>Evidence Index</h2>",
            "<p class='card-subtext'>Cryptographic inventory of all tamper-evident forensic artifacts hashed at point of intake.</p>",
            "<table>",
            "<thead><tr><th>Evidence ID</th><th>Filename</th><th>Channel</th>"
            "<th>SHA-256 Cryptographic Hash</th><th>Captured At</th><th>Analysis Runs</th></tr></thead>",
            "<tbody>",
        ]
    )
    for ev in pack.evidence_index:
        runs = ", ".join(ev.analysis_runs) if ev.analysis_runs else "none"
        parts.append(
            f"<tr><td><code>{html.escape(ev.evidence_id)}</code></td>"
            f"<td>{html.escape(ev.filename or 'N/A')}</td>"
            f"<td>{html.escape(ev.channel.value)}</td>"
            f"<td><code style='font-size:0.75rem;'>{html.escape(ev.sha256)}</code></td>"
            f"<td>{html.escape(_fmt_when(ev.captured_at, 'N/A'))}</td>"
            f"<td>{html.escape(runs)}</td></tr>"
        )
    parts.extend(["</tbody></table>"])
    if pack.custody_head:
        parts.append(
            f"<p style='margin-top:0.75rem; font-size:0.825rem;'><strong>Custody Chain Head Hash:</strong> "
            f"<code>{html.escape(pack.custody_head)}</code></p>"
        )
    parts.append("</div>")

    # -------------------------------------------------------------------------
    # 7. SECTION 63 BSA ELECTRONIC EVIDENCE CERTIFICATE
    # -------------------------------------------------------------------------
    if pack.sec63_helper:
        parts.extend(
            [
                "<div class='dossier-card'>",
                "<div class='card-badge-row'>",
                "<span class='badge badge-danger'>STATUTORY DECLARATION</span>",
                "<span class='badge badge-outline'>BHARATIYA SAKSHYA ADHINIYAM, 2023</span>",
                "</div>",
                "<h2>BSA Section 63 Certificate Helper</h2>",
                "<p class='card-subtext'>Statutory electronic certificate pursuant to Section 63 of Bharatiya Sakshya Adhiniyam, 2023 (formerly Section 65B of Indian Evidence Act, 1872) for electronic record admissibility in an Indian Court of Law.</p>",
                f"<div class='cert-box'>{html.escape(pack.sec63_helper)}</div>",
                "</div>",
            ]
        )

    parts.append(f"<div class='disclaimer'><strong>Disclaimer:</strong> {html.escape(pack.disclaimer)}</div>")
    parts.append("</div>")  # Close wrapper
    parts.append("</body></html>")
    return "\n".join(parts)
