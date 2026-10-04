"""Trusted internal data: vendor master, payment history, employee directory. CONTRACT FILE.

These come from the company's own ERP/HRMS exports (CSV in the demo). They are TRUSTED:
they are the only inputs (together with the maker-entered transaction) that set the floor.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from satyapan.contracts.common import AccountNumber, Gstin, Ifsc, Model, UpiId
from satyapan.contracts.enums import Role


class BankAccount(Model):
    account_number: AccountNumber
    ifsc: Ifsc
    bank_name: str


class Vendor(Model):
    vendor_id: str = Field(pattern=r"^V\d{3,}$")
    legal_name: str
    gstin: Gstin | None = None
    status: Literal["active", "inactive"] = "active"
    email_domain: str
    phone_on_file: str
    accounts: list[BankAccount] = Field(default_factory=list)
    upi_ids: list[UpiId] = Field(default_factory=list)

    def has_account(self, account_number: str | None, ifsc: str | None, upi_id: str | None) -> bool:
        """True if the payee details match one of this vendor's registered details.

        A bank transfer matches only if BOTH account number and IFSC match one account.
        A UPI transfer matches if the UPI ID is registered.
        """
        if upi_id:
            return upi_id in self.upi_ids
        if account_number and ifsc:
            return any(a.account_number == account_number and a.ifsc == ifsc for a in self.accounts)
        return False


class PaymentHistoryRow(Model):
    vendor_id: str
    paid_on: date
    amount_inr: int = Field(ge=0)
    utr: str


class VendorStats(Model):
    """Derived from payment history, used by the floor (K1 vs K2)."""

    vendor_id: str
    max_amount_12m: int = Field(ge=0)
    days_since_last_paid: int | None  # None = never paid


class Employee(Model):
    employee_id: str = Field(pattern=r"^emp_[a-z0-9_]+$")
    name: str
    email: str
    title: str
    roles: list[Role]
    phone_on_file: str
    is_senior_approver: bool = False
    active: bool = True


class MasterChange(Model):
    """A requested change to a trust anchor (T1). Always floor HOLD."""

    target: Literal["vendor_phone", "vendor_email", "vendor_bank", "approver_list"]
    vendor_id: str | None = None
    old_value: str
    new_value: str
    requested_via: str  # e.g. "email from accounts@narmada-logistics.example"
