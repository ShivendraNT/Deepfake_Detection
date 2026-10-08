"""Regex extraction of payment fields from invoice text. TASK T08.

Spec: docs/tasks/T08-invoice-pdf-checker.md.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import TypeVar

from satyapan.contracts.parsed import InvoiceFields

IFSC_PATTERN = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
# Lookarounds stop "billing@kaveri-packaging.example" (an email) from matching as a UPI id.
UPI_PATTERN = re.compile(r"(?<![\w.\-])[\w.\-]+@[a-z]+(?![\w\-@]|\.\w)")
GSTIN_PATTERN = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
# Account numbers: 9-18 digits that appear within ~40 characters AFTER one of these keywords.
ACCOUNT_KEYWORDS = ("a/c", "account", "acct", "khata", "खाता")
ACCOUNT_DIGITS = re.compile(r"\b\d{9,18}\b")
# Amount: "Total", "Amount Payable", "Grand Total" followed by ₹/Rs/INR and digits with commas.
AMOUNT_PATTERN = re.compile(
    r"(?:grand total|total amount|amount payable|total)\s*[:\-]?\s*"
    r"(?:₹|rs\.?|inr)\s*([\d,]+)(?:\.\d{1,2})?",
    re.IGNORECASE,
)
INVOICE_NO_PATTERN = re.compile(r"invoice\s*(?:no\.?|number|#)\s*[:\-]?\s*([A-Z0-9/\-]+)", re.I)
# One combined keyword search (case-insensitive). Only digits within ACCOUNT_WINDOW
# characters after a hit are treated as an account number.
ACCOUNT_KEYWORD_PATTERN = re.compile(
    "|".join(re.escape(keyword) for keyword in ACCOUNT_KEYWORDS), re.IGNORECASE
)
ACCOUNT_WINDOW = 40

_T = TypeVar("_T")


def _unique(values: Iterable[_T]) -> list[_T]:
    """De-duplicate, keeping the first-seen order."""
    return list(dict.fromkeys(values))


def _account_numbers(text: str) -> list[str]:
    """Digits that sit in the ACCOUNT_WINDOW characters right after a payment keyword."""
    found: list[str] = []
    for hit in ACCOUNT_KEYWORD_PATTERN.finditer(text):
        window = text[hit.end() : hit.end() + ACCOUNT_WINDOW]
        found.extend(ACCOUNT_DIGITS.findall(window))
    return _unique(found)


def extract_invoice_fields(text: str) -> InvoiceFields:
    """Apply the patterns above. De-duplicate, keep first-seen order.

    - UPI: use UPI_PATTERN as given (handle after '@' is letters only, e.g. 'kaveripack@fakeupi';
      email addresses are excluded by the lookarounds).
    - Account numbers: only digits found near ACCOUNT_KEYWORDS (case-insensitive), so phone
      numbers and GSTIN digits are not picked up.
    - Amounts: int rupees (drop commas and paise).
    """
    amounts = _unique(int(raw.replace(",", "")) for raw in AMOUNT_PATTERN.findall(text))
    invoice_no = INVOICE_NO_PATTERN.search(text)
    return InvoiceFields(
        ifsc_codes=_unique(IFSC_PATTERN.findall(text)),
        account_numbers=_account_numbers(text),
        upi_ids=_unique(UPI_PATTERN.findall(text)),
        gstins=_unique(GSTIN_PATTERN.findall(text)),
        amounts_inr=amounts,
        invoice_number=invoice_no.group(1) if invoice_no else None,
    )
