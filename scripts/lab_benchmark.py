"""Run the Forensic Lab on the investigation dataset and score it against ground truth.

    uv run python scripts/lab_benchmark.py          # = make lab-benchmark

Loads data/forensics/demo through the normal intake (a temporary lab store), waits for every
analysis, then compares each verdict with manifest.json's ground truth:
  synthetic   -> correct if SYNTHETIC; "flagged" if SUSPICIOUS / MANIPULATED
  manipulated -> correct if MANIPULATED; "flagged" if SUSPICIOUS / SYNTHETIC
  authentic   -> correct if NO_INDICATORS; a false alarm if SYNTHETIC / MANIPULATED
Writes results/forensics_demo_benchmark.{json,md}. Small and scripted by design: the large-
sample error rates are in docs/forensics/VALIDATION.md.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "results" / "forensics_demo_benchmark.json"
OUT_MD = ROOT / "results" / "forensics_demo_benchmark.md"


def grade(truth: str, label: str) -> str:
    if truth == "synthetic":
        return "correct" if label == "SYNTHETIC" else "flagged" if label in ("SUSPICIOUS", "MANIPULATED") else "missed"
    if truth == "manipulated":
        return "correct" if label == "MANIPULATED" else "flagged" if label in ("SUSPICIOUS", "SYNTHETIC") else "missed"
    if label in ("SYNTHETIC", "MANIPULATED"):
        return "false alarm"
    return "correct" if label == "NO_INDICATORS" else "cautious"


def main() -> int:
    from satyapan.forensics.demo import DEMO_DIR, load_demo_case
    from satyapan.forensics.service import LabService
    from satyapan.forensics.store import LabStore

    manifest = json.loads((DEMO_DIR / "manifest.json").read_text())
    truth = {it["file"]: it for it in manifest["items"]}
    with tempfile.TemporaryDirectory() as tmp:
        svc = LabService(store=LabStore(Path(tmp)), workers=2)
        t0 = time.time()
        view = load_demo_case(svc)
        cid = view["case"]["id"]
        while True:
            evs = svc.store.case_evidence(cid)
            if all(e.status.value in ("done", "error") for e in evs):
                break
            time.sleep(1)
        wall = time.time() - t0
        rows = []
        for e in evs:
            a = svc.store.analysis(e.id)
            v = a.verdict if a else None
            label = v.label.value if v else "ERROR"
            gt = truth[e.filename]["ground_truth"]
            secs = sum(t.duration_ms for t in a.techniques) / 1000 if a else 0.0
            rows.append({"exhibit": e.exhibit, "file": e.filename, "truth": gt, "verdict": label,
                         "risk_index": v.risk_index if v else None, "grade": grade(gt, label),
                         "headline": v.headline if v else e.headline,
                         "key": v.rationale[:3] if v else [], "seconds": round(secs, 1)})  # fmt: skip
        links = [{"kind": ln.kind.value, "source": ln.source, "target": ln.target,
                  "score": ln.score} for ln in svc.store.links(cid)]  # fmt: skip
        svc.pool.shutdown(wait=True)
    rows.sort(key=lambda r: (r["exhibit"][0] != "Q", int(r["exhibit"][1:])))
    summary = {g: sum(r["grade"] == g for r in rows) for g in ("correct", "flagged", "cautious", "missed", "false alarm")}
    res = {"dataset": manifest["name"], "wall_seconds": round(wall, 1), "summary": summary, "rows": rows, "links": links}
    OUT_JSON.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    lines = [
        "# Forensic Lab on the investigation dataset",
        "",
        f"`make lab-benchmark` — {len(rows)} exhibits, {wall:.0f} s wall time on this machine. "
        f"Correct {summary['correct']}, flagged-but-not-conclusive {summary['flagged']}, cautious "
        f"(inconclusive on a genuine item) {summary['cautious']}, missed {summary['missed']}, "
        f"false alarms {summary['false alarm']}.",
        "",
        "| Exhibit | File | Ground truth | Verdict | Risk | Grade | Strongest findings |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        key = "; ".join(r["key"]).replace("|", "/")
        lines.append(f"| {r['exhibit']} | `{r['file']}` | {r['truth']} | **{r['verdict']}** | "
                     f"{r['risk_index']} | {r['grade']} | {key} |")  # fmt: skip
    lines += ["", f"Cross-exhibit links found: {len(links)} "
              f"({', '.join(sorted({ln['kind'] for ln in links}))})."]  # fmt: skip
    OUT_MD.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if summary["false alarm"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
