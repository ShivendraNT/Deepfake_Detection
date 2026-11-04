"""One-command forensic demo: intake -> analysis -> report, on the committed `demo_kit/`.

    uv run python scripts/forensic_demo.py            # fast path, no large models
    uv run python scripts/forensic_demo.py --heavy    # also run GenD / XLS-R if installed
    uv run python scripts/forensic_demo.py --serve    # then print how to open the dashboard

It seals the six demo exhibits as read-only originals, runs every M2/M3/M4 check on working
copies, compares each overall finding with `demo_kit/manifest.json`, writes the PDF/HTML/MD/JSON
report and exits non-zero if an expectation is not met. Nothing leaves the machine.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from satyapan.forensics.locker import ForensicLocker, is_readonly  # noqa: E402
from satyapan.forensics.pipeline import (  # noqa: E402
    analyze_case,
    infer_source_and_media_type,
)
from satyapan.forensics.report import generate_forensic_report  # noqa: E402

DEMO_KIT = ROOT / "demo_kit"
CASE_ID = "case_forensic_demo"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "vault_data" / "forensic_demo"))
    ap.add_argument("--heavy", action="store_true", help="run GenD / voice models if installed")
    ap.add_argument("--serve", action="store_true", help="print dashboard instructions")
    a = ap.parse_args(argv)

    manifest = json.loads((DEMO_KIT / "manifest.json").read_text(encoding="utf-8"))
    out_root = Path(a.out)
    case_dir = out_root / CASE_ID
    if case_dir.exists():
        shutil.rmtree(case_dir)

    locker = ForensicLocker(
        case_dir,
        collector="examiner_arjun",
        case_meta={
            "title": "Digital Impersonation & Manipulated Multimedia Evidence (Demo)",
            "agency": "National Cyber Forensic Laboratory (Demo Unit)",
            "examiner": "Arjun Mehta (Senior Digital Forensic Examiner)",
            "fir_reference": "FIR-2026-CYB-0419 (Demo)",
        },
    )
    print(f"Case: {CASE_ID}  (offline, {len(manifest['items'])} exhibits)")

    for it in manifest["items"]:
        fpath = DEMO_KIT / it["filename"]
        source_type, media_type = infer_source_and_media_type(it["filename"])
        item = locker.intake(
            fpath,
            source_type=source_type,
            media_type=media_type,
            device=it["device"],
            device_info=it["device_info"],
        )
        ok_hash = item.sha256 == it["sha256"]
        ok_ro = is_readonly(item.stored_path)
        print(
            f"  sealed {item.evidence_id} {item.original_name:42s} "
            f"sha256 {'match' if ok_hash else 'MISMATCH'}  read-only {'yes' if ok_ro else 'NO'}"
        )
        if not (ok_hash and ok_ro):
            print("intake integrity check failed", file=sys.stderr)
            return 2

    analysis = analyze_case(locker, use_heavy_models=a.heavy)

    print("\nFindings")
    failures = 0
    by_id = {r["evidence_id"]: r for r in analysis["items"]}
    for it in manifest["items"]:
        rep = by_id[it["evidence_id"]]
        expected = it["expected_overall_finding"]
        got = rep["overall_finding"]
        ok = got == expected
        failures += int(not ok)
        mark = "PASS" if ok else "FAIL"
        print(
            f"  [{mark}] {rep['evidence_id']} {rep['original_name']:42s} "
            f"{got:34s} conf {rep['overall_confidence']:.2f}"
        )
        if not ok:
            print(f"         expected: {expected}")
        print(f"         {rep['overall_statement']}")

    integ = analysis["integrity"]
    print(
        f"\nLocker integrity: {integ['status']}  "
        f"merkle {integ['merkle_root'][:24]}...  chain {integ['chain_head'][:24]}..."
    )
    print(f"Custody entries: {len(analysis['custody_log'])} (Ed25519 signed)")
    print(f"Timeline events: {len(analysis['timeline'])}")

    bundle = generate_forensic_report(locker)
    print("\nReport")
    for key in ("pdf_path", "html_path", "md_path", "json_path"):
        print(f"  {key[:-5]:9s} {bundle[key]}")
    cert = bundle["certificate"]
    print(
        f"  Section 63 BSA 2023 draft: {len(cert['records'])} records, "
        f"Merkle root matches anchor: {cert['part_b']['merkle']['matches_anchor']}"
    )

    if a.serve:
        print("\nOpen the workstation:")
        print("  make run         # or: uvicorn --app-dir src satyapan.api.app:app --port 8000")
        print("  http://127.0.0.1:8000/forensics  ->  'Load Demo Case'")

    if failures:
        print(f"\n{failures} exhibit(s) did not match the manifest expectation", file=sys.stderr)
        return 1
    print("\nmake demo: ALL GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
