"""Screen an evidence dump: rank every image by forensic risk and cluster near-duplicates.

    uv run python scripts/forensics_scan.py path/to/dump
    uv run python scripts/forensics_scan.py path/to/dump --csv triage.csv --json triage.json
    uv run python scripts/forensics_scan.py path/to/dump --limit 20

Nothing is sealed or stored. For formal work, intake the files into a case so custody is recorded.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from satyapan.forensics.triage import DEFAULT_DUPLICATE_HAMMING, triage_paths  # noqa: E402

COLUMNS = [
    "rank",
    "risk",
    "finding",
    "duplicate_group",
    "file",
    "sha256",
    "whole_image",
    "tampering",
    "provenance",
    "source_attribution",
    "c2pa",
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folder", help="folder of files to screen")
    ap.add_argument("--csv", help="also write a CSV here")
    ap.add_argument("--json", help="also write the full JSON here")
    ap.add_argument("--limit", type=int, default=30, help="rows to print (default 30)")
    ap.add_argument("--duplicate-hamming", type=int, default=DEFAULT_DUPLICATE_HAMMING)
    a = ap.parse_args(argv)

    folder = Path(a.folder)
    if not folder.exists():
        print(f"not found: {folder}", file=sys.stderr)
        return 2

    report = triage_paths(
        [p for p in folder.rglob("*") if p.is_file()],
        duplicate_hamming=a.duplicate_hamming,
    )
    items = report["items"]

    print(
        f"Screened {report['files_screened']} file(s), {report['images_screened']} image(s) in "
        f"{report['seconds']}s ({report['files_per_second']}/s). "
        f"High risk: {report['high_risk']}, verify: {report['verify']}, "
        f"duplicate groups: {len(report['duplicate_groups'])}"
    )
    print()
    header = f"{'#':>3}  {'risk':>4}  {'finding':30s} {'grp':>3}  file"
    print(header)
    print("-" * len(header))
    for i, it in enumerate(items[: a.limit], 1):
        grp = it["duplicate_group"] if it["duplicate_group"] else "-"
        print(f"{i:3d}  {it['risk']:4.2f}  {it['finding']:30s} {grp!s:>3}  {Path(it['path']).name}")
        for reason in it["reasons"][:2]:
            print(f"         - {reason[:150]}")

    if report["duplicate_groups"]:
        print(
            "\nNear-duplicate groups (dHash Hamming <= "
            f"{a.duplicate_hamming}; the same picture after re-encoding)"
        )
        for gid, members in report["duplicate_groups"].items():
            print(f"  group {gid}:")
            for m in members:
                print(f"    {Path(m).name}")

    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(COLUMNS)
            for i, it in enumerate(items, 1):
                m = it["metrics"]
                w.writerow(
                    [
                        i,
                        it["risk"],
                        it["finding"],
                        it["duplicate_group"] or "",
                        it["path"],
                        it["sha256"],
                        m.get("whole_image"),
                        m.get("tampering"),
                        m.get("provenance"),
                        m.get("source_attribution"),
                        m.get("c2pa"),
                    ]
                )
        print(f"\nCSV: {a.csv}")

    if a.json:
        Path(a.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"JSON: {a.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
