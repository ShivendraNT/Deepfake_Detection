"""PDF text + metadata. TASK T08 — docs/tasks/T08-invoice-pdf-checker.md.

Text via pdfplumber (text layer only; no OCR in the MVP — Textract cannot read Hindi).
"""

from __future__ import annotations

from datetime import datetime

from satyapan.contracts.parsed import PdfMeta


def extract_pdf_text(data: bytes) -> str:
    """Concatenate page.extract_text() for all pages with '\\n'. Raise ValueError if not a PDF."""
    raise NotImplementedError("T08: see docs/tasks/T08-invoice-pdf-checker.md")


def parse_pdf_date(value: str | None) -> datetime | None:
    """Parse PDF dates like "D:20261001103000+05'30'" -> aware datetime. None if missing/bad."""
    raise NotImplementedError("T08: see docs/tasks/T08-invoice-pdf-checker.md")


def read_pdf_metadata(data: bytes) -> PdfMeta:
    """eof_count = number of b"%%EOF" markers; incremental_updates = max(eof_count - 1, 0).
    producer/creator/creation_date/mod_date from the document info (pdfplumber .metadata).
    """
    raise NotImplementedError("T08: see docs/tasks/T08-invoice-pdf-checker.md")
