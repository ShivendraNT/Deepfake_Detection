"""PDF text + metadata. TASK T08 — docs/tasks/T08-invoice-pdf-checker.md.

Text via pdfplumber (text layer only; no OCR in the MVP — Textract cannot read Hindi).
"""

from __future__ import annotations

import io
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import pdfplumber

from satyapan.contracts.parsed import PdfMeta

PDF_HEADER = b"%PDF"
PDF_DATE_PATTERN = re.compile(r"D:(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})([+-])(\d{2})'(\d{2})'")
# Keys of the document info dictionary we care about.
INFO_KEYS = ("Producer", "Creator", "CreationDate", "ModDate")
_INFO_VALUE = {
    key: re.compile(rb"/" + key.encode("ascii") + rb"\s*\(([^)]*)\)") for key in INFO_KEYS
}


def extract_pdf_text(data: bytes) -> str:
    """Concatenate page.extract_text() for all pages with '\\n'. Raise ValueError if not a PDF."""
    _require_pdf(data)
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def parse_pdf_date(value: str | None) -> datetime | None:
    """Parse PDF dates like "D:20261001103000+05'30'" -> aware datetime. None if missing/bad."""
    if not value:
        return None
    match = PDF_DATE_PATTERN.search(value)
    if match is None:
        return None
    year, month, day, hour, minute, second = (int(part) for part in match.groups()[:6])
    sign = 1 if match.group(7) == "+" else -1
    offset = timedelta(hours=int(match.group(8)), minutes=int(match.group(9)))
    try:
        return datetime(year, month, day, hour, minute, second, tzinfo=timezone(sign * offset))
    except ValueError:
        return None


def read_pdf_metadata(data: bytes) -> PdfMeta:
    """eof_count = number of b"%%EOF" markers; incremental_updates = max(eof_count - 1, 0).
    producer/creator/creation_date/mod_date from the document info (pdfplumber .metadata).

    For an incrementally-updated file pdfminer resolves the info object to its FIRST occurrence,
    so .metadata still shows the pre-edit dictionary; the appended update (bytes after the first
    %%EOF) is the effective one and is used instead.
    """
    _require_pdf(data)
    eof_count = data.count(b"%%EOF")
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        info = {str(key): _as_text(value) for key, value in (pdf.metadata or {}).items()}
    if eof_count > 1:
        info.update(_appended_info(data))
    return PdfMeta(
        eof_count=eof_count,
        incremental_updates=max(eof_count - 1, 0),
        producer=info.get("Producer"),
        creator=info.get("Creator"),
        creation_date=parse_pdf_date(info.get("CreationDate")),
        mod_date=parse_pdf_date(info.get("ModDate")),
    )


def _require_pdf(data: bytes) -> None:
    if not data.startswith(PDF_HEADER):
        raise ValueError("not a PDF: missing %PDF header")


def _as_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("latin-1", errors="replace")
    return str(value)


def _appended_info(data: bytes) -> dict[str, str]:
    """Info keys of the update appended after the first %%EOF (later definitions win)."""
    appended = data.split(b"%%EOF", 1)[1]
    found: dict[str, str] = {}
    for key, pattern in _INFO_VALUE.items():
        match = pattern.search(appended)
        if match:
            found[key] = match.group(1).decode("latin-1", errors="replace")
    return found
