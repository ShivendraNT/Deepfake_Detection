"""Batch examination from the command line (triage of a seized folder, scripted runs).

    uv run python -m satyapan.forensics.cli EXHIBITS... [--title T] [--fir F] [--reference R...]
                                            [--report] [--examiner NAME] [--json OUT.json]

Every file (folders are walked) goes through the same intake as the dashboard: hashed first,
stored write-once in the lab store (SATYAPAN_LAB_DIR, default ./lab_data), logged in the
custody chain, analysed, cross-linked; a PDF report is written on request. Exit code 0 when
every exhibit was analysed, 2 if any analysis failed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from satyapan.forensics.models import EvidenceRole

COLOURS = {"SYNTHETIC": "\033[91m", "MANIPULATED": "\033[93m", "SUSPICIOUS": "\033[33m",
           "NO_INDICATORS": "\033[92m", "INCONCLUSIVE": "\033[90m"}  # fmt: skip
RESET = "\033[0m"


def collect(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            out += sorted(f for f in p.rglob("*") if f.is_file() and not f.name.startswith("."))
        elif p.is_file():
            out.append(p)
        else:
            print(f"not found: {p}", file=sys.stderr)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Satyapan Forensic Lab — batch examination")
    ap.add_argument("exhibits", nargs="+", help="files or folders to examine (questioned)")
    ap.add_argument("--reference", nargs="*", default=[], help="known/reference samples")
    ap.add_argument("--title", default="Batch examination")
    ap.add_argument("--fir", default="")
    ap.add_argument("--report", action="store_true", help="write a PDF report")
    ap.add_argument("--examiner", default="examiner")
    ap.add_argument("--json", dest="json_out", default="", help="write the full case export")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args(argv)
    from satyapan.forensics.service import LabService

    svc = LabService(workers=2)
    case = svc.create_case(actor=args.examiner, title=args.title, fir_number=args.fir)
    print(f"case {case.id} — lab store {svc.store.root}")
    for role, files in ((EvidenceRole.REFERENCE, collect(args.reference)),
                        (EvidenceRole.QUESTIONED, collect(args.exhibits))):  # fmt: skip
        for f in files:
            ev, dup = svc.add_evidence(case.id, f.read_bytes(), f.name, actor=args.examiner,
                                       role=role, received_from=str(f.parent), analyze=False)  # fmt: skip
            print(f"  {'dup ' if dup else 'in  '}{ev.exhibit:4s} {ev.sha256[:16]}…  {f}")
    failed = 0
    for ev in svc.store.case_evidence(case.id):
        try:
            a = svc.analyze_now(ev.id, args.examiner)
            v = a.verdict
            assert v is not None
            col = "" if args.no_color else COLOURS.get(v.label.value, "")
            print(f"{ev.exhibit:4s} {col}{v.label.value:13s}{'' if args.no_color else RESET} "
                  f"risk {v.risk_index:3d}  {ev.filename[:40]:40s} {v.headline}")  # fmt: skip
            for line in v.rationale[:4]:
                print(f"       · {line}")
        except Exception as exc:  # noqa: BLE001 - report and continue with the next exhibit
            failed += 1
            print(f"{ev.exhibit:4s} FAILED        {ev.filename}: {exc}")
    for ln in svc.store.links(case.id):
        print(f"link  {ln.kind.value:15s} {ln.source[-6:]} ↔ {ln.target[-6:]}  {ln.detail[:90]}")
    chain = svc.store.verify_chain()
    print(f"custody chain: {'INTACT' if chain.ok else 'BROKEN'} ({chain.rows_checked} rows)")
    if args.report:
        from satyapan.forensics.report.builder import generate_report

        rec = generate_report(svc, case.id, [], args.examiner, "", "", args.examiner)
        print(f"report: {svc.store.report_path(case.id, rec['id'])}  sha256 {rec['sha256']}")
    if args.json_out:
        view = svc.case_view(case.id)
        view["analyses"] = {e["id"]: (a.model_dump(mode="json") if (a := svc.store.analysis(e["id"]))
                                      else None) for e in view["evidence"]}  # fmt: skip
        Path(args.json_out).write_text(json.dumps(view, indent=1, default=str))
        print(f"export: {args.json_out}")
    svc.pool.shutdown(wait=True)
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
