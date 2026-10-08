"""Compare invoice fields with the vendor master and the pending payment. TASK T08."""

from __future__ import annotations

from satyapan.contracts.common import mask_account
from satyapan.contracts.enums import GreyReason, ReasonCode, SignalSource
from satyapan.contracts.evidence import DetectorOutput, Signal
from satyapan.contracts.master import Vendor
from satyapan.contracts.parsed import InvoiceFields, PdfMeta
from satyapan.contracts.transaction import PaymentAction
from satyapan.master.store import MasterData

DETECTOR_NAME = "document_checker"
DETECTOR_VERSION = "0.1.0"


def document_signals(
    fields: InvoiceFields,
    meta: PdfMeta | None,
    master: MasterData,
    txn: PaymentAction | None,
    evidence_id: str,
) -> DetectorOutput:
    """Rules:
    - Find the vendor: master.vendor(txn.vendor_id) if txn else match by GSTIN in fields.
    - If the vendor is known and ANY account/IFSC/UPI in the invoice is not registered for
      that vendor -> DOC_ACCOUNT_MISMATCH (detail: {"field": "ifsc"|"account"|"upi",
      "invoice_value_masked": "••••1234"}). Never put full account numbers in detail.
    - If meta and meta.incremental_updates > 0 and mod_date > creation_date -> DOC_PDF_EDITED.
    - If nothing fired -> DOC_NO_ISSUES (info only).
    - If no payment field could be extracted at all -> grey_reasons += [PARSE_FAILURE].
    All signals: Signal.make(code, source=SignalSource.DETERMINISTIC, evidence_ids=[evidence_id],
    detector=DETECTOR_NAME).
    """
    signals: list[Signal] = []
    grey_reasons: list[GreyReason] = []

    def add(code: ReasonCode, detail: dict[str, object] | None = None) -> None:
        signals.append(
            Signal.make(
                code,
                source=SignalSource.DETERMINISTIC,
                evidence_ids=[evidence_id],
                detector=DETECTOR_NAME,
                detail=detail,
            )
        )

    vendor = _vendor_for(fields, master, txn)
    if vendor is not None:
        unregistered = _unregistered_field(vendor, fields)
        if unregistered is not None:
            field, value = unregistered
            add(
                ReasonCode.DOC_ACCOUNT_MISMATCH,
                {"field": field, "invoice_value_masked": _masked(field, value)},
            )

    if meta is not None and meta.incremental_updates > 0 and _modified_after_creation(meta):
        add(
            ReasonCode.DOC_PDF_EDITED,
            {"eof_count": meta.eof_count, "producer": meta.producer},
        )

    if not (fields.ifsc_codes or fields.account_numbers or fields.upi_ids):
        # Nothing to compare with the master: grey, never PASS.
        grey_reasons.append(GreyReason.PARSE_FAILURE)

    if not signals and not grey_reasons:
        add(ReasonCode.DOC_NO_ISSUES)

    return DetectorOutput(
        detector=DETECTOR_NAME,
        version=DETECTOR_VERSION,
        evidence_id=evidence_id,
        signals=signals,
        grey_reasons=grey_reasons,
        artifacts={
            "vendor_id": vendor.vendor_id if vendor else None,
            "invoice_number": fields.invoice_number,
            "gstins": fields.gstins,
            "amounts_inr": fields.amounts_inr,
            "ifsc_codes": fields.ifsc_codes,
            "upi_ids": fields.upi_ids,
            "account_numbers_masked": [mask_account(a) for a in fields.account_numbers],
            "eof_count": meta.eof_count if meta else 0,
        },
    )


def _vendor_for(
    fields: InvoiceFields, master: MasterData, txn: PaymentAction | None
) -> Vendor | None:
    """The vendor this invoice belongs to: the maker's choice first, else the GSTIN on the bill."""
    vendor = master.vendor(txn.vendor_id) if txn is not None else None
    if vendor is not None:
        return vendor
    for gstin in fields.gstins:
        for candidate in master.vendors.values():
            if candidate.gstin is not None and candidate.gstin == gstin:
                return candidate
    return None


def _unregistered_field(vendor: Vendor, fields: InvoiceFields) -> tuple[str, str] | None:
    """First invoice payee detail that the vendor master does not know, if any."""
    accounts = {account.account_number for account in vendor.accounts}
    ifscs = {account.ifsc for account in vendor.accounts}
    upi_ids = set(vendor.upi_ids)
    for account in fields.account_numbers:
        if account not in accounts:
            return "account", account
    for ifsc in fields.ifsc_codes:
        if ifsc not in ifscs:
            return "ifsc", ifsc
    for upi in fields.upi_ids:
        if upi not in upi_ids:
            return "upi", upi
    return None


def _modified_after_creation(meta: PdfMeta) -> bool:
    """True when the document changed after it was created.

    A ModDate later than CreationDate proves it. When there are no dates to compare we still
    count the appended update (incremental_updates > 0, checked by the caller) as a change:
    a weak, inconclusive signal is cheaper than a missed edit.
    """
    if meta.mod_date is None or meta.creation_date is None:
        return True
    return meta.mod_date > meta.creation_date


def _masked(field: str, value: str) -> str:
    """Detail values are always masked: accounts by contract, IFSC/UPI the same way."""
    if field == "upi" and "@" in value:
        return "••••@" + value.rsplit("@", 1)[-1]
    return mask_account(value)
