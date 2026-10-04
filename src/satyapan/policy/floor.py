"""The deterministic floor (C2 -> C9). PRE-IMPLEMENTED (T02).

INVARIANT: the floor depends ONLY on trusted inputs: the case kind, the maker-entered
transaction / master change, the vendor master and the config. It never sees messages,
documents, audio, signals or LLM output. tests/invariants/test_floor_isolation.py checks
this by inspecting the signature and by fuzzing untrusted inputs.
"""

from __future__ import annotations

from satyapan.contracts.enums import ActionType, Band, CaseKind
from satyapan.contracts.master import MasterChange
from satyapan.contracts.transaction import PaymentAction
from satyapan.master.store import MasterData
from satyapan.policy.config import PolicyConfig


def compute_floor(
    kind: CaseKind,
    txn: PaymentAction | None,
    master_change: MasterChange | None,
    master: MasterData,
    cfg: PolicyConfig,
) -> tuple[Band, ActionType]:
    """Return (floor_band, action_type). See the floor table in docs/ARCHITECTURE.md §6.

    | Action | Definition                                                     | Floor  |
    | T1     | change to a trust anchor                                       | HOLD   |
    | D1     | data/credential request, no payment                            | PASS   |
    | C1     | existing active vendor, payee details differ from master       | VERIFY |
    | N1     | new beneficiary, amount <= de-minimis                          | PASS   |
    | N2     | new beneficiary, amount > de-minimis                           | VERIFY |
    | K2     | known payee, amount > 1.25 x 12-month max, or dormant > 180 d  | VERIFY |
    | K1     | known payee, unchanged details, in pattern                     | PASS   |
    """
    if kind == CaseKind.MASTER_CHANGE or master_change is not None:
        return Band.HOLD, ActionType.T1
    if kind == CaseKind.DATA_REQUEST:
        return Band.PASS, ActionType.D1
    if txn is None:  # LIVE_CALL before any payment exists
        return Band.PASS, ActionType.NONE

    vendor = master.vendor(txn.vendor_id)
    if vendor is None and txn.vendor_id is None:
        # Maker did not pick a vendor: match by registered payee details if possible.
        vendor = master.vendor_by_payee(txn.account_number, txn.ifsc, txn.upi_id)

    if vendor is None or not vendor.has_account(txn.account_number, txn.ifsc, txn.upi_id):
        if vendor is not None and vendor.status == "active":
            return Band.VERIFY, ActionType.C1  # existing vendor, NEW bank/UPI details
        if txn.amount_inr > cfg.de_minimis_inr:
            return Band.VERIFY, ActionType.N2
        return Band.PASS, ActionType.N1

    stats = master.stats(vendor.vendor_id, as_of=txn.created_at.date())
    dormant = stats.days_since_last_paid is None or stats.days_since_last_paid > cfg.dormant_days
    if txn.amount_inr > cfg.pattern_multiplier * stats.max_amount_12m or dormant:
        return Band.VERIFY, ActionType.K2
    return Band.PASS, ActionType.K1
