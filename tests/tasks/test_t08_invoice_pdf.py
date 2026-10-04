"""T08 acceptance: invoice text regex, PDF metadata, master diff on 6 fixture PDFs (2 edited)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from satyapan.document.checker import document_signals
from satyapan.document.extract import extract_invoice_fields
from satyapan.document.pdf import extract_pdf_text, parse_pdf_date, read_pdf_metadata

pytestmark = pytest.mark.task("T08")

INV = Path(__file__).resolve().parents[2] / "data" / "demo" / "invoices"
EXPECTED = json.loads((INV / "expected.json").read_text(encoding="utf-8"))


def test_regex_on_plain_text() -> None:
    text = (
        "GSTIN: 00FAKEV0001A1Z5\nInvoice No: KDP/2026/0917\nTotal Amount: Rs. 2,10,000\n"
        "Account No: 99990000001111   IFSC: FAKA0000111\nUPI: kaveripack@fakeupi\n"
        "Contact: +91-00000-10001 / billing@kaveri-packaging.example"
    )
    f = extract_invoice_fields(text)
    assert f.ifsc_codes == ["FAKA0000111"]
    assert f.account_numbers == ["99990000001111"]
    assert f.upi_ids == ["kaveripack@fakeupi"]  # the email address is NOT a UPI id
    assert f.gstins == ["00FAKEV0001A1Z5"]
    assert f.amounts_inr == [210000]
    assert f.invoice_number == "KDP/2026/0917"


def test_phone_digits_not_account() -> None:
    assert extract_invoice_fields("Phone 9999000011 Ref 123456789012").account_numbers == []


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_fixture_pdf_fields_meta_and_signals(master, name: str) -> None:
    exp = EXPECTED[name]
    data = (INV / name).read_bytes()
    fields = extract_invoice_fields(extract_pdf_text(data))
    assert fields.model_dump() == exp["fields"]
    meta = read_pdf_metadata(data)
    assert meta.eof_count == exp["eof_count"]
    assert meta.incremental_updates == exp["eof_count"] - 1
    out = document_signals(fields, meta, master, None, "ev_test")
    assert sorted(s.code.value for s in out.signals) == sorted(exp["signals"])
    for s in out.signals:
        for v in s.detail.values():
            assert not (isinstance(v, str) and v.isdigit() and len(v) >= 9), (
                "never put full account numbers in detail"
            )


def test_pdf_date_parsing() -> None:
    d = parse_pdf_date("D:20261001103000+05'30'")
    assert d is not None and d.year == 2026 and d.utcoffset() is not None
    assert parse_pdf_date(None) is None and parse_pdf_date("garbage") is None


def test_not_a_pdf_raises_value_error() -> None:
    with pytest.raises(ValueError):
        extract_pdf_text(b"hello")
