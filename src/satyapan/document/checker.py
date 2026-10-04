"""Compare invoice fields with the vendor master and the pending payment. TASK T08."""

from __future__ import annotations

from satyapan.contracts.evidence import DetectorOutput
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
    raise NotImplementedError("T08: see docs/tasks/T08-invoice-pdf-checker.md")
