"""`satya scan`: run Satya on any files the judges (or anyone) hand over, offline.

    uv run python scripts/satya.py scan KIT_FOLDER [more files...] [--lang hi] [--out report]
    (= uv run python -m satyapan.check_cli ...)

Every file gets exactly the consumer Scam Check page's answer: the quick check (all detectors
on this laptop, band from the policy engine, nothing kept), raised by the impossible-claim
rules on the file's words. Prints one line per file and
writes <out>.csv + <out>.md. If a file name starts with "real"/"genuine"/"legit" or
"fake"/"scam"/"spoof", the expected answer is read from it and the summary counts hits.
"""

from __future__ import annotations

import argparse
import csv
import mimetypes
import sys
import time
from pathlib import Path

from satyapan.contracts.enums import Band, Lang

BAD = ("fake", "scam", "spoof", "phish", "fraud", "deepfake", "clone")
GOOD = ("real", "genuine", "legit", "ham", "bonafide")
FLAG = {Band.VERIFY, Band.HOLD}


def expected(name: str) -> str | None:
    n = name.lower()
    if n.startswith(BAD):
        return "flag"
    if n.startswith(GOOD):
        return "pass"
    return None


def files_in(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            out += sorted(
                f
                for f in p.rglob("*")
                if f.is_file() and not f.name.startswith(".") and f.name != "kit_manifest.json"
            )
        elif p.is_file():
            out.append(p)
        else:
            print(f"skipped (not found): {p}", file=sys.stderr)
    return out


def with_rules(r, f: Path) -> tuple[Band, list[str]]:
    """The consumer page's answer: the quick check's band, raised (never lowered) by the
    impossible-claim rules on whatever words the file holds (satyapan.citizen.check)."""
    from satyapan.citizen.rules import scam_check
    from satyapan.contracts.enums import Channel
    from satyapan.policy.bands import rank

    words = r.transcript or (
        f.read_text(encoding="utf-8", errors="replace") if r.channel == Channel.MANUAL else ""
    )
    if not words.strip():
        return r.band, []
    rules = scam_check(words)
    return (rules.band if rank(rules.band) > rank(r.band) else r.band), rules.rule_hits


def grade(rows: list[dict]) -> list[str]:
    """Per-channel summary of the files whose name says what they are (Markdown lines)."""
    graded = [r for r in rows if r.get("expected")]
    if not graded:
        return []
    out = ["| Channel | fakes / scams flagged | genuine passed | right |", "|---|---|---|---|"]
    for ch in [*sorted({r["channel"] for r in graded}), "ALL"]:
        sub = [r for r in graded if ch in ("ALL", r["channel"])]
        fakes = [r for r in sub if r["expected"] == "flag"]
        reals = [r for r in sub if r["expected"] == "pass"]
        ok = sum(r["correct"] == "True" for r in sub)
        caught = sum(r["correct"] == "True" for r in fakes)
        passed = sum(r["correct"] == "True" for r in reals)
        out.append(f"| {ch} | {caught}/{len(fakes)} | {passed}/{len(reals)} | {ok}/{len(sub)} |")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="satya scan", description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--lang", choices=["en", "hi"], default="en")
    ap.add_argument("--out", default="satya_check_report")
    a = ap.parse_args(argv)

    from satyapan.api.state import AppState
    from satyapan.quickcheck import quick_check
    from satyapan.settings import Settings

    files = files_in(a.paths)
    if not files:
        print("no files to check", file=sys.stderr)
        return 2
    t0 = time.perf_counter()
    state = AppState.build(Settings())
    print(f"engine ready in {time.perf_counter() - t0:.1f} s; checking {len(files)} file(s)\n")
    lang = Lang.HI if a.lang == "hi" else Lang.EN
    rows = []
    for f in files:
        mime = mimetypes.guess_type(f.name)[0] or ""
        try:
            r = quick_check(state, f.read_bytes(), f.name, mime, lang)
        except Exception as exc:  # noqa: BLE001 - one bad file must not stop the run
            print(f"{f.name:40.40}  ERROR {exc}")
            rows.append({"file": f.name, "verdict": "ERROR", "why": str(exc)[:200]})
            continue
        band, hits = with_rules(r, f)
        exp = expected(f.name)
        got = "flag" if band in FLAG else "pass"
        mark = "" if exp is None else (" ok" if exp == got else " MISS")
        findings = "; ".join(f"{k}={v}" for k, v in r.findings.items())
        print(f"{f.name:40.40}  {band.value:6}  {r.channel.value:10} {r.seconds:5.1f}s  "
              f"{findings}{mark}")  # fmt: skip
        for line in r.why[:3]:
            print(f"{'':42}- {line[:110]}")
        if r.not_checked:
            print(f"{'':42}! not checked here: {', '.join(r.not_checked)}")
        rows.append({
            "file": f.name, "channel": r.channel.value, "verdict": band.value,
            "rule_hits": " ".join(hits),
            "expected": exp or "", "correct": "" if exp is None else str(exp == got),
            "reasons": " ".join(c.value for c in r.reason_codes),
            "info": " ".join(c.value for c in r.info_codes), "findings": findings,
            "not_checked": "; ".join(r.not_checked), "seconds": r.seconds,
            "why": " | ".join(r.why), "sha256": r.sha256,
        })  # fmt: skip
    summary = grade(rows)
    if summary:
        print("\n" + "\n".join(summary))
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(f"{a.out}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    with open(f"{a.out}.md", "w", encoding="utf-8") as fh:
        if summary:
            fh.write("\n".join(summary) + "\n\n")
        fh.write(
            "| File | Verdict | Expected | Why | Not checked | s |\n|---|---|---|---|---|---|\n"
        )
        for r in rows:
            fh.write(f"| {r['file']} | {r['verdict']} | {r.get('expected', '')} | "
                     f"{r.get('reasons', '')} | {r.get('not_checked', '')} | "
                     f"{r.get('seconds', '')} |\n")  # fmt: skip
    print(f"\nreport: {a.out}.csv, {a.out}.md (nothing else was kept)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
