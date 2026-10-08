"""Trusted master data (C2): vendor master, payment history, employee directory.

PRE-IMPLEMENTED (T01). Loads the CSV exports in data/demo/ (in production: ERP/HRMS exports).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from satyapan.contracts.enums import Role
from satyapan.contracts.master import (
    BankAccount,
    Employee,
    OutgoingPayment,
    PaymentHistoryRow,
    Vendor,
    VendorStats,
)


@dataclass
class MasterData:
    vendors: dict[str, Vendor] = field(default_factory=dict)
    history: list[PaymentHistoryRow] = field(default_factory=list)
    employees: dict[str, Employee] = field(default_factory=dict)
    company_domain: str = "demo-industries.example"
    # Payments already sent to payees NOT in the vendor master (bank statement / ERP payment
    # register). Trusted. Feeds the 30-day de-minimis aggregation (ADR-022).
    new_payee_payments: list[OutgoingPayment] = field(default_factory=list)

    # ---- vendors ----
    def vendor(self, vendor_id: str | None) -> Vendor | None:
        if vendor_id is None:
            return None
        return self.vendors.get(vendor_id)

    def vendor_by_payee(
        self, account_number: str | None, ifsc: str | None, upi_id: str | None
    ) -> Vendor | None:
        """Vendor whose registered details match (used when the maker left vendor_id empty)."""
        for v in self.vendors.values():
            if v.has_account(account_number, ifsc, upi_id):
                return v
        return None

    def stats(self, vendor_id: str, as_of: date) -> VendorStats:
        """max amount paid in the 365 days before `as_of`, and days since the last payment."""
        rows = [r for r in self.history if r.vendor_id == vendor_id and r.paid_on <= as_of]
        window_start = as_of - timedelta(days=365)
        recent = [r.amount_inr for r in rows if r.paid_on > window_start]
        last = max((r.paid_on for r in rows), default=None)
        return VendorStats(
            vendor_id=vendor_id,
            max_amount_12m=max(recent, default=0),
            days_since_last_paid=None if last is None else (as_of - last).days,
        )

    def paid_to_new_payee(
        self,
        account_number: str | None,
        ifsc: str | None,
        upi_id: str | None,
        as_of: date,
        window_days: int,
    ) -> int:
        """Sum already paid to this (non-master) payee in the `window_days` up to `as_of`."""
        if window_days <= 0:
            return 0
        start = as_of - timedelta(days=window_days)
        return sum(
            p.amount_inr
            for p in self.new_payee_payments
            if start < p.paid_on <= as_of and p.same_payee(account_number, ifsc, upi_id)
        )

    def known_domains(self) -> set[str]:
        """Domains we trust as 'ours' or 'our vendors' (for look-alike checks, T04)."""
        return {v.email_domain.lower() for v in self.vendors.values()} | {
            self.company_domain.lower()
        }

    # ---- employees ----
    def employee(self, employee_id: str | None) -> Employee | None:
        if employee_id is None:
            return None
        return self.employees.get(employee_id)

    def employee_by_email(self, email: str) -> Employee | None:
        email = email.lower()
        for e in self.employees.values():
            if e.email.lower() == email:
                return e
        return None

    def senior_approvers(self) -> list[Employee]:
        return [e for e in self.employees.values() if e.is_senior_approver and e.active]


def _read_csv(path: Path) -> Iterable[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        yield from csv.DictReader(fh)


def load_vendors(path: Path) -> dict[str, Vendor]:
    """One CSV row per (vendor, account). Rows with the same vendor_id are merged."""
    vendors: dict[str, Vendor] = {}
    for row in _read_csv(path):
        vid = row["vendor_id"]
        v = vendors.get(vid)
        if v is None:
            v = Vendor(
                vendor_id=vid,
                legal_name=row["legal_name"],
                gstin=row.get("gstin") or None,
                status="active" if row.get("status", "active") == "active" else "inactive",
                email_domain=row["email_domain"],
                phone_on_file=row["phone_on_file"],
            )
            vendors[vid] = v
        if row.get("account_number"):
            v.accounts.append(
                BankAccount(
                    account_number=row["account_number"],
                    ifsc=row["ifsc"],
                    bank_name=row.get("bank_name", ""),
                )
            )
        if row.get("upi_id"):
            v.upi_ids.append(row["upi_id"])
    return vendors


def load_history(path: Path) -> list[PaymentHistoryRow]:
    return [
        PaymentHistoryRow(
            vendor_id=r["vendor_id"],
            paid_on=date.fromisoformat(r["paid_on"]),
            amount_inr=int(r["amount_inr"]),
            utr=r["utr"],
        )
        for r in _read_csv(path)
    ]


def load_new_payee_payments(path: Path) -> list[OutgoingPayment]:
    """Optional CSV: paid_on,amount_inr,account_number,ifsc,upi_id,utr (empty file = none)."""
    if not path.exists():
        return []
    return [
        OutgoingPayment(
            paid_on=date.fromisoformat(r["paid_on"]),
            amount_inr=int(r["amount_inr"]),
            account_number=r.get("account_number") or None,
            ifsc=r.get("ifsc") or None,
            upi_id=r.get("upi_id") or None,
            utr=r["utr"],
        )
        for r in _read_csv(path)
    ]


def load_employees(path: Path) -> dict[str, Employee]:
    out: dict[str, Employee] = {}
    for r in _read_csv(path):
        out[r["employee_id"]] = Employee(
            employee_id=r["employee_id"],
            name=r["name"],
            email=r["email"],
            title=r["title"],
            roles=[Role(x) for x in r["roles"].split("|") if x],
            phone_on_file=r["phone_on_file"],
            is_senior_approver=r.get("is_senior_approver", "false").lower() == "true",
            active=r.get("active", "true").lower() == "true",
        )
    return out


def load_master(data_dir: Path) -> MasterData:
    """Load data/demo/{vendor_master,payment_history,employees}.csv (+ optional
    new_payee_payments.csv)."""
    return MasterData(
        vendors=load_vendors(data_dir / "vendor_master.csv"),
        history=load_history(data_dir / "payment_history.csv"),
        employees=load_employees(data_dir / "employees.csv"),
        new_payee_payments=load_new_payee_payments(data_dir / "new_payee_payments.csv"),
    )
