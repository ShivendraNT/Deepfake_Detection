"""Synthetic master data + payment cases for the alert-budget benchmark.

Everything is fictional (vendors 'Demo Supplier NNN', accounts 9999..., IFSC FAK..., *.example)
and DETERMINISTIC: choices use sha256 of a key, not an RNG, so the same code always builds the
same cases (no `random` anywhere; see tests/harness/test_results_provenance.py).
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, TypeVar

from research.heldout.stats import split_of
from satyapan.contracts import (
    BankAccount,
    Case,
    CaseKind,
    Channel,
    Employee,
    Evidence,
    PaymentAction,
    PaymentHistoryRow,
    PaymentRail,
    Role,
    Vendor,
)
from satyapan.master.store import MasterData

T = TypeVar("T")
DEMO_DAY = datetime.fromisoformat("2026-10-05T10:00:00+05:30")
N_VENDORS = 40


def h(key: str) -> int:
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16)


def pick(key: str, seq: Sequence[T]) -> T:
    return seq[h(key) % len(seq)]


def frac(key: str) -> float:
    """Deterministic number in [0, 1) derived from a key."""
    return (h(key) % 10_000) / 10_000


def vendor_id(i: int) -> str:
    return f"V{100 + i}"


def account_of(i: int) -> tuple[str, str]:
    return f"9999{5000000000 + i:010d}", f"FAKS0{100000 + i:06d}"


def base_amount(i: int) -> int:
    return 20_000 + int(frac(f"base{i}") * 480_000) // 100 * 100


def build_master() -> MasterData:
    vendors: dict[str, Vendor] = {}
    history: list[PaymentHistoryRow] = []
    for i in range(N_VENDORS):
        acct, ifsc = account_of(i)
        vid = vendor_id(i)
        vendors[vid] = Vendor(
            vendor_id=vid,
            legal_name=f"Demo Supplier {100 + i} Pvt Ltd",
            email_domain=f"supplier{100 + i}.example",
            phone_on_file=f"+91-00000-4{i:04d}",
            accounts=[BankAccount(account_number=acct, ifsc=ifsc, bank_name="Fictional Bank S")],
        )
        for m in range(12):
            amt = int(base_amount(i) * (0.8 + 0.4 * frac(f"hist{i}-{m}"))) // 100 * 100
            history.append(
                PaymentHistoryRow(
                    vendor_id=vid,
                    paid_on=DEMO_DAY.date() - timedelta(days=12 + 30 * m),
                    amount_inr=amt,
                    utr=f"FAKEUTR9{i:03d}{m:05d}",
                )
            )
    employees = {
        "emp_priya": Employee(
            employee_id="emp_priya",
            name="Priya Sharma",
            email="priya@demo-industries.example",
            title="AP Executive",
            roles=[Role.MAKER],
            phone_on_file="+91-00000-20001",
        ),
        "emp_rajesh": Employee(
            employee_id="emp_rajesh",
            name="Rajesh Iyer",
            email="rajesh@demo-industries.example",
            title="CFO",
            roles=[Role.REQUESTER, Role.CHECKER],
            phone_on_file="+91-00000-20003",
            is_senior_approver=True,
        ),
    }
    return MasterData(vendors=vendors, history=history, employees=employees)


@dataclass
class SynthCase:
    case: Case
    payloads: list[bytes]
    group: str  # "routine" | "attack"
    scenario: str
    split: str  # "dev" | "test"
    gold_asks: list[str]
    prior_new_payee_payments: list[dict[str, Any]] = dataclasses.field(default_factory=list)


def _evidence(case_id: str, j: int, text: str, channel: str) -> tuple[Evidence, bytes]:
    data = text.encode("utf-8")
    ch = Channel.WHATSAPP_TEXT if channel in ("whatsapp", "sms") else Channel.MANUAL
    ev = Evidence(
        id=f"ev_{case_id}_{j}",
        case_id=f"case_{case_id}",
        channel=ch,
        media_type="text/plain",
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        captured_at=DEMO_DAY,
        submitted_by="emp_priya",
        storage_uri=f"mem://{case_id}/{j}",
        excerpt=text[:200],
    )
    return ev, data


def _case(
    case_id: str, kind: CaseKind, txn: PaymentAction | None, msgs: list[tuple[str, str]]
) -> tuple[Case, list[bytes]]:
    evs = [_evidence(case_id, j, t, ch) for j, (t, ch) in enumerate(msgs)]
    case = Case(
        id=f"case_{case_id}",
        title=case_id,
        kind=kind,
        created_at=DEMO_DAY,
        created_by="emp_priya",
        txn=txn,
        evidence=[e for e, _ in evs],
    )
    return case, [d for _, d in evs]


def _txn(case_id: str, **kw: Any) -> PaymentAction:
    return PaymentAction(
        id=f"txn_{case_id}",
        rail=PaymentRail.NEFT,
        created_by="emp_priya",
        created_at=DEMO_DAY,
        **kw,
    )


def routine_cases(benign: list[dict[str, Any]], per_split: int = 200) -> list[SynthCase]:
    """Known vendor, registered account, in-pattern amount (floor K1), 1-3 benign messages
    drawn from the SAME split of benign_ap.jsonl."""
    out: list[SynthCase] = []
    for split in ("dev", "test"):
        pool = [b for b in benign if split_of(b["id"]) == split]
        for n in range(per_split):
            cid = f"r_{split}_{n:03d}"
            i = h(cid) % N_VENDORS
            acct, ifsc = account_of(i)
            amount = int(base_amount(i) * (0.7 + 0.4 * frac(cid + "amt"))) // 100 * 100
            k = 1 + h(cid + "k") % 3
            chosen: list[dict[str, Any]] = []
            for j in range(k):
                b = pick(f"{cid}-{j}", pool)
                if b not in chosen:
                    chosen.append(b)
            txn = _txn(
                cid,
                vendor_id=vendor_id(i),
                beneficiary_name=f"Demo Supplier {100 + i} Pvt Ltd",
                account_number=acct,
                ifsc=ifsc,
                amount_inr=amount,
            )
            case, payloads = _case(
                cid, CaseKind.PAYMENT, txn, [(b["text"], b["channel"]) for b in chosen]
            )
            out.append(SynthCase(case, payloads, "routine", "K1_routine", split, []))
    return out


FOOTER_IDS = ("ben-001", "ben-002", "ben-005", "ben-010", "ben-014", "ben-029")


def attack_cases(asks: list[dict[str, Any]], benign: list[dict[str, Any]]) -> list[SynthCase]:
    """One case per held-out attacker ask. The payment shape follows the ask:
    A7 -> known vendor paid to NEW bank details (C1); A1 / A4 / A5 -> new beneficiary,
    large amount (N2); A6 -> new beneficiary, small amount (N1); A2 / A3 only -> no payment
    (LIVE_CALL for calls, DATA_REQUEST otherwise). Half of the e-mail asks get a standard
    confidentiality footer appended (attackers' mails carry footers too)."""
    footers = {b["id"]: b["text"] for b in benign if b["id"] in FOOTER_IDS}
    out: list[SynthCase] = []
    for r in asks:
        cid = f"a_{r['id'].replace('-', '_')}"
        gold = r["asks"]
        text = r["text"]
        if r["channel"] == "email" and h(cid + "footer") % 2 == 0:
            ft = pick(cid + "f", sorted(footers.values()))
            text = f"{text} Regards, Accounts. {ft.split('. ', 1)[-1]}"
        i = h(cid) % N_VENDORS
        new_acct = f"9999{8000000000 + h(cid) % 1_000_000_000:010d}"
        new_ifsc = f"FAKX0{h(cid + 'i') % 1_000_000:06d}"
        kind, txn, scen = CaseKind.PAYMENT, None, ""
        if "A7" in gold:
            scen = "C1_payee_change"
            txn = _txn(
                cid,
                vendor_id=vendor_id(i),
                beneficiary_name=f"Demo Supplier {100 + i} Pvt Ltd",
                account_number=new_acct,
                ifsc=new_ifsc,
                amount_inr=int(base_amount(i) * 0.9) // 100 * 100,
            )
        elif "A6" in gold and "A1" not in gold:
            scen = "N1_small_new_payee"
            txn = _txn(
                cid,
                beneficiary_name="Demo Gift Desk",
                account_number=new_acct,
                ifsc=new_ifsc,
                amount_inr=5_000 + h(cid + "a") % 19_000,
            )
        elif {"A1", "A4", "A5", "A6"} & set(gold):
            scen = "N2_new_payee_large"
            txn = _txn(
                cid,
                beneficiary_name="Demo Escrow Services",
                account_number=new_acct,
                ifsc=new_ifsc,
                amount_inr=200_000 + h(cid + "a") % 4_600_000,
                requested_by_employee_id="emp_rajesh",
            )
        else:  # A2 / A3 only
            scen = "no_payment_credential_or_remote"
            kind = CaseKind.LIVE_CALL if r["channel"] == "call" else CaseKind.DATA_REQUEST
        case, payloads = _case(cid, kind, txn, [(text, r["channel"])])
        out.append(SynthCase(case, payloads, "attack", scen, split_of(r["id"]), list(gold)))
    return out


def splitting_cases(per_split: int = 6) -> list[SynthCase]:
    """De-minimis splitting: a new beneficiary already received 1-3 payments just under the
    de-minimis in the last 30 days (payer's own payment register); today's payment is also
    just under it. No message. Judge finding b5."""
    out: list[SynthCase] = []
    for split in ("dev", "test"):
        for n in range(per_split):
            cid = f"s_{split}_{n:02d}"
            acct = f"9999{7000000000 + n + (0 if split == 'dev' else 100):010d}"
            ifsc = "FAKY0000777"
            prior = [
                {
                    "paid_on": (DEMO_DAY.date() - timedelta(days=3 + 7 * j)).isoformat(),
                    "amount_inr": 24_000 + 100 * j,
                    "account_number": acct,
                    "ifsc": ifsc,
                    "utr": f"FAKEUTR7{n:03d}{j:02d}{split[0]}",
                }
                for j in range(1 + h(cid) % 3)
            ]
            txn = _txn(
                cid,
                beneficiary_name="Demo Split Payee",
                account_number=acct,
                ifsc=ifsc,
                amount_inr=24_500,
            )
            case, payloads = _case(cid, CaseKind.PAYMENT, txn, [])
            out.append(SynthCase(case, payloads, "attack", "N1_split_payments", split, [], prior))
    return out


def as_of(d: str) -> date:
    return date.fromisoformat(d)
