"""Build the UTR-first report pack. TASK T16 — docs/tasks/T16-report-pack.md.

There is NO public 1930/NCRP API. This module only produces text/JSON/HTML drafts that a
human copies into the portal, reads out on the 1930 call, or emails to the bank.
It must not import any network library (tests/invariants/test_no_auto_reporting.py).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from satyapan.contracts.case import Case
from satyapan.contracts.custody import CustodyRow
from satyapan.contracts.report import ReportPack
from satyapan.master.store import MasterData

Variant = Literal["ATTEMPTED", "MONEY_SENT"]


class ReportNotUnlockedError(PermissionError):
    """The pack is unlocked only by SUSPECTED_FRAUD (ATTEMPTED) or CONFIRMED_FRAUD (MONEY_SENT)."""


def format_inr(amount: int) -> str:
    """Indian digit grouping: 4850000 -> '₹48,50,000'; 620000 -> '₹6,20,000'."""
    raise NotImplementedError("T16: see docs/tasks/T16-report-pack.md")


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
    raise NotImplementedError("T16: see docs/tasks/T16-report-pack.md")


def render_html(pack: ReportPack) -> str:
    """Printable HTML. html.escape() EVERY value (evidence may contain attacker text).
    The 1930 script (if any) comes first, then bank email, NCRP draft, evidence index."""
    raise NotImplementedError("T16: see docs/tasks/T16-report-pack.md")
