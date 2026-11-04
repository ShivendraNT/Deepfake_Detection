"""M7 tests: End-to-end test on committed `demo_kit/`, golden-file test for Section 63 certificate,
adversarial robustness tests, and module test-coverage audit."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.make_forensic_demo_kit import DEMO_KIT_DIR, FIXED_TIME

from satyapan.forensics.locker import ForensicEvidenceItem, ForensicLocker, is_readonly
from satyapan.forensics.pipeline import analyze_case, infer_source_and_media_type
from satyapan.forensics.report import generate_forensic_report
from satyapan.forensics.section63 import (
    build_section63_certificate,
    render_section63_markdown,
)

ROOT = Path(__file__).resolve().parents[2]


def test_every_forensic_module_has_dedicated_tests() -> None:
    """Target: no module in `src/satyapan/forensics/` without tests."""
    forensic_modules = {
        p.stem
        for p in (ROOT / "src" / "satyapan" / "forensics").glob("*.py")
        if p.name != "__init__.py"
    }
    test_contents = "\n".join(
        p.read_text(encoding="utf-8") for p in (ROOT / "tests" / "forensics").glob("test_*.py")
    )
    for mod in forensic_modules:
        assert f"satyapan.forensics.{mod}" in test_contents or mod in test_contents, (
            f"Forensic module {mod}.py is not covered by tests/forensics/"
        )


def test_golden_file_section63_certificate_matches_committed_golden() -> None:
    manifest = json.loads((DEMO_KIT_DIR / "manifest.json").read_text(encoding="utf-8"))
    ev_items = [
        ForensicEvidenceItem(
            evidence_id=it["evidence_id"],
            case_id="case_demo_kit",
            original_name=it["filename"],
            stored_path=f"originals/{it['evidence_id']}__{it['filename']}",
            working_path=f"working/{it['evidence_id']}__{it['filename']}",
            sha256=it["sha256"],
            size_bytes=it["size_bytes"],
            media_type="application/octet-stream",
            source_type=it["source_type"],
            device=it["device"],
            collector="examiner_arjun",
            collected_at_utc=FIXED_TIME,
            device_info=it["device_info"],
        )
        for it in manifest["items"]
    ]
    cert = build_section63_certificate(
        ev_items,
        {"name": "Arjun Mehta", "role": "Senior Digital Forensic Examiner"},
        examiner={
            "name": "Arjun Mehta",
            "designation": "Senior Digital Forensic Examiner",
            "organisation": "National Cyber Forensic Laboratory",
        },
        integrity={
            "ok": True,
            "chain_head": "a" * 64,
            "custody_entries": 18,
            "records": [{"evidence_id": i.evidence_id, "sha256": i.sha256} for i in ev_items],
            "anchor": {
                "merkle_root": build_section63_certificate(ev_items)["part_b"]["merkle"]["root"],
                "chain_head": "a" * 64,
                "anchored_at_utc": FIXED_TIME.isoformat(),
            },
            "signers": [{"signer": "examiner_arjun", "public_key_sha256": "b" * 64}],
        },
        generated_at_utc=FIXED_TIME.isoformat(),
    )
    rendered = render_section63_markdown(cert)
    golden = (DEMO_KIT_DIR / "golden_section63.md").read_text(encoding="utf-8")
    assert rendered == golden


def test_end_to_end_intake_analysis_and_report_on_committed_demo_kit(tmp_path: Path) -> None:
    manifest = json.loads((DEMO_KIT_DIR / "manifest.json").read_text(encoding="utf-8"))
    locker = ForensicLocker(
        tmp_path / "case_e2e_demo_kit",
        collector="examiner_arjun",
        case_meta={"title": "Demo Kit End-to-End Verification"},
    )

    for it in manifest["items"]:
        fpath = DEMO_KIT_DIR / it["filename"]
        assert fpath.exists(), f"Missing demo kit exhibit: {fpath}"
        stype, mtype = infer_source_and_media_type(it["filename"])
        sealed = locker.intake(
            fpath,
            source_type=stype,
            media_type=mtype,
            device=it["device"],
            device_info=it["device_info"],
        )
        assert sealed.sha256 == it["sha256"]
        assert is_readonly(sealed.stored_path)

    case_analysis = analyze_case(locker, use_heavy_models=False)
    assert case_analysis["integrity"]["ok"] is True
    assert len(case_analysis["items"]) == len(manifest["items"])

    by_id = {r["evidence_id"]: r for r in case_analysis["items"]}
    for it in manifest["items"]:
        eid = it["evidence_id"]
        assert by_id[eid]["overall_finding"] == it["expected_overall_finding"], (
            f"Unexpected finding on {eid} ({it['filename']})"
        )
        assert case_analysis["merkle_proofs"][eid]["verified"] is True

    bundle = generate_forensic_report(locker, fixed_timestamp="2026-10-24T12:00:00+00:00")
    for k in ("pdf_path", "html_path", "md_path", "json_path"):
        assert Path(bundle[k]).exists()
        assert Path(bundle[k]).stat().st_size > 500
