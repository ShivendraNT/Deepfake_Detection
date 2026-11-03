"""M6 tests: Automated forensic report (PDF, HTML, Markdown, JSON), Section 63 BSA 2023 Parts A & B
certificate, embedded visual evidence images, and byte-level reproducibility."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pdfplumber
from fastapi.testclient import TestClient

from satyapan.api.app import create_app
from satyapan.forensics.pipeline import seed_demo_forensic_case
from satyapan.forensics.report import generate_forensic_report


def _sha(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_forensic_report_completeness_pdf_extraction_and_reproducibility(tmp_path: Path) -> None:
    locker = seed_demo_forensic_case(tmp_path, "case_m6_repro", use_heavy_models=False)

    # First generation
    b1 = generate_forensic_report(locker)
    md_sha1 = _sha(b1["md_path"])
    json_sha1 = _sha(b1["json_path"])
    html_sha1 = _sha(b1["html_path"])
    pdf_sha1 = _sha(b1["pdf_path"])

    # Second generation from the stored case data must be byte-for-byte identical
    b2 = generate_forensic_report(locker)
    assert _sha(b2["md_path"]) == md_sha1
    assert _sha(b2["json_path"]) == json_sha1
    assert _sha(b2["html_path"]) == html_sha1
    assert _sha(b2["pdf_path"]) == pdf_sha1

    md_text = Path(b1["md_path"]).read_text(encoding="utf-8")
    for required in (
        "Schedule of Sealed Multimedia Evidence & SHA-256 Hashes",
        "Cryptographic Chain of Custody",
        "Forensic Methodology",
        "Detailed Per-Exhibit Forensic Findings",
        "Known Limitations of This Analysis",
        "Section 63 (Bharatiya Sakshya Adhiniyam, 2023) - Part A Certificate (DRAFT)",
        "Section 63 (Bharatiya Sakshya Adhiniyam, 2023) - Part B Expert Certificate (DRAFT)",
        "Examiner Sign-Off & Peer Review Block",
        "OFFICIAL SEAL OF FORENSIC LAB",
    ):
        assert required in md_text, f"Missing required section in Markdown report: {required}"

    # Verify PDF structure, extracted text via pdfplumber, and embedded DCTDecode images
    pdf_bytes = Path(b1["pdf_path"]).read_bytes()
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"/Subtype /Image" in pdf_bytes
    assert b"/Filter /DCTDecode" in pdf_bytes

    with pdfplumber.open(b1["pdf_path"]) as pdf:
        assert len(pdf.pages) >= 4
        extracted = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert "case_m6_repro" in extracted
    assert "Bharatiya Sakshya Adhiniyam, 2023" in extracted
    assert "DRAFT" in extracted
    assert "Examiner Sign-Off" in extracted
    for item in locker.items():
        assert item.evidence_id in extracted


def test_forensic_report_api_endpoints(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SATYAPAN_FORENSIC_CASES_DIR", str(tmp_path / "fcases"))
    client = TestClient(create_app())

    client.post("/api/forensics/demo-case")

    r_pdf = client.get("/api/forensics/cases/case_forensic_demo_01/report?format=pdf")
    assert r_pdf.status_code == 200
    assert r_pdf.headers["content-type"] == "application/pdf"
    assert r_pdf.content.startswith(b"%PDF-1.4")

    r_html = client.get("/api/forensics/cases/case_forensic_demo_01/report?format=html")
    assert r_html.status_code == 200
    assert "data:image/png;base64," in r_html.text

    r_md = client.get("/api/forensics/cases/case_forensic_demo_01/report?format=md")
    assert r_md.status_code == 200
    assert "Section 63 (Bharatiya Sakshya Adhiniyam, 2023)" in r_md.text

    r_json = client.get("/api/forensics/cases/case_forensic_demo_01/report?format=json")
    assert r_json.status_code == 200
    j = r_json.json()
    assert j["case_id"] == "case_forensic_demo_01"
    assert len(j["section63_certificate"]["records"]) == 4
