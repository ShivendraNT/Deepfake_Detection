"""The pending payment (maker-entered, TRUSTED for floor purposes). CONTRACT FILE."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from satyapan.contracts.common import AccountNumber, Ifsc, Model, UpiId, mask_account
from satyapan.contracts.enums import PaymentRail


class PaymentAction(Model):
    """A pending (or already-sent) payment. The maker types this in; nobody parses it from email.

    Example JSON (see data/demo/cases/*.json):
        {"id": "txn_s07", "vendor_id": "V002", "beneficiary_name": "Narmada Demo Logistics",
         "account_number": "99992222009917", "ifsc": "FAKC0000991", "upi_id": null,
         "amount_inr": 284000, "rail": "NEFT", "debit_account_masked": "••••1234",
         "requested_by_employee_id": null, "bank_shown_payee_name": null,
         "created_by": "emp_priya", "created_at": "2026-10-05T10:00:00+05:30"}
    """

    id: str = Field(pattern=r"^txn_[A-Za-z0-9_\-]+$")
    vendor_id: str | None = None  # None = maker says this is a new beneficiary
    beneficiary_name: str
    account_number: AccountNumber | None = None
    ifsc: Ifsc | None = None
    upi_id: UpiId | None = None
    beneficiary_bank: str | None = None
    amount_inr: int = Field(ge=0)
    rail: PaymentRail
    debit_account_masked: str = "••••0000"
    requested_by_employee_id: str | None = None  # claimed internal requester (e.g. CFO)
    bank_shown_payee_name: str | None = None  # typed by maker from the bank's name lookup
    created_by: str
    created_at: datetime
    # Filled only if money already left (golden-hour report pack):
    utr: str | None = None
    sent_at: datetime | None = None

    @model_validator(mode="after")
    def _payee_present(self) -> PaymentAction:
        has_bank = self.account_number is not None and self.ifsc is not None
        if not has_bank and self.upi_id is None:
            raise ValueError("PaymentAction needs (account_number AND ifsc) OR upi_id")
        return self

    @property
    def beneficiary_masked(self) -> str:
        if self.upi_id:
            return self.upi_id
        return f"A/c {mask_account(self.account_number)} ({self.ifsc})"
