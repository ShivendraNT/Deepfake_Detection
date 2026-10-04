"""Clearance requirements: what must happen before a payment may proceed. PRE-IMPLEMENTED (T02).

Clearing SATISFIES a band; it never LOWERS it. The callback number always comes from the
vendor master or the employee directory — never from a message, document or call.
"""

from __future__ import annotations

from typing import Literal

from satyapan.contracts.case import Case, ClearanceRequirement
from satyapan.contracts.enums import ActionType, Band, ClearanceMethod, Role
from satyapan.master.store import MasterData
from satyapan.policy.config import PolicyConfig

NumberSource = Literal["vendor_master", "vendor_master_old", "directory", "independent_source"]


def requester_id(case: Case) -> str | None:
    if case.txn is not None and case.txn.requested_by_employee_id:
        return case.txn.requested_by_employee_id
    if case.oob is not None:
        return case.oob.requester_employee_id
    return None


def resolve_callback_number(
    case: Case, master: MasterData, action: ActionType
) -> tuple[str | None, NumberSource]:
    """Pick the callback number from TRUSTED data only."""
    vendor = None
    if case.txn is not None:
        vendor = master.vendor(case.txn.vendor_id) or master.vendor_by_payee(
            case.txn.account_number, case.txn.ifsc, case.txn.upi_id
        )
    elif case.master_change is not None:
        vendor = master.vendor(case.master_change.vendor_id)
    if vendor is not None:
        old = action in (ActionType.C1, ActionType.T1)
        return vendor.phone_on_file, ("vendor_master_old" if old else "vendor_master")
    emp = master.employee(requester_id(case))
    if emp is not None:
        return emp.phone_on_file, "directory"
    return None, "independent_source"


def clearance_rules(
    band: Band, action: ActionType, case: Case, master: MasterData, cfg: PolicyConfig
) -> ClearanceRequirement:
    if band == Band.PASS:
        return ClearanceRequirement(band=band, mode="none")

    number, source = resolve_callback_number(case, master, action)
    notes: list[str] = []
    if number is None:
        notes.append(
            "No trusted number on file: obtain one from an independent source "
            "(vendor onboarding KYC). Never use a number from the message or call."
        )
    oob_possible = requester_id(case) is not None

    if band == Band.HOLD:
        if action == ActionType.T1:
            methods = [ClearanceMethod.CHECKER_CALLBACK, ClearanceMethod.SECOND_APPROVER]
            notes.append("Trust-anchor change: verify via the OLD channel; second approver needed.")
        else:
            methods = [ClearanceMethod.CHECKER_CALLBACK, ClearanceMethod.SECURITY_ACK]
            notes.append("HOLD: only the checker can clear. OOB-Confirm alone is not enough.")
        return ClearanceRequirement(
            band=band,
            who=[Role.CHECKER],
            methods=methods,
            mode="all",
            callback_number=number,
            callback_number_source=source,
            notes=notes,
        )

    # VERIFY
    who = [Role.MAKER, Role.CHECKER]
    if action == ActionType.C1:
        methods = [ClearanceMethod.CALLBACK_MASTER_NUMBER, ClearanceMethod.BANK_NAME_MATCH]
        notes.append(
            "Call back on the OLD on-file number. Type the payee name the bank shows; "
            "it must match the vendor's legal name."
        )
        mode: Literal["any", "all"] = "all"
    elif action == ActionType.N2 and case.txn is not None and case.txn.amount_inr > cfg.t_high_inr:
        methods = [ClearanceMethod.CALLBACK_MASTER_NUMBER, ClearanceMethod.OOB_CONFIRM]
        mode = "all"
        notes.append("New beneficiary above ₹10 lakh: callback AND OOB-Confirm.")
        if not oob_possible:
            methods = [ClearanceMethod.CALLBACK_MASTER_NUMBER, ClearanceMethod.CHECKER_CALLBACK]
            notes.append("No internal requester on record, so the checker also calls back.")
    else:
        methods = [ClearanceMethod.CALLBACK_MASTER_NUMBER]
        if oob_possible:
            methods.append(ClearanceMethod.OOB_CONFIRM)
        mode = "any"
    return ClearanceRequirement(
        band=band,
        who=who,
        methods=methods,
        mode=mode,
        callback_number=number,
        callback_number_source=source,
        notes=notes,
    )
