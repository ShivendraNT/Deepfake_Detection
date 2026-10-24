"""Judge kit — score the shipped detector stack, then run it on a judge's own input.

    uv run python scripts/judge_kit.py
    uv run python scripts/judge_kit.py --text "transfer to the new account, keep it quiet"
    uv run python scripts/judge_kit.py --file path/to/invoice.pdf --vendor-id V001
    uv run python scripts/judge_kit.py --file path/to/message.eml --new-payee --amount 4800000
    uv run python scripts/judge_kit.py --screen --text "Account 9999000099917 ..."

What the scoreboard measures (all local, no network, no real customer data):
  1. Ask detection on the pre-registered held-out TEST split: frozen lexicon, context layer,
     and the shipped product configuration (context + live phrasebook).
  2. The real decision path on synthetic payment cases: routine false alarms at HOLD, attack
     catch at >= VERIFY, and the per-scenario failures (alert budget).
  3. The communication checkers on the labelled fixtures: e-mail signals and invoice/PDF signals
     (exact-match functional checks, not a generalisation claim).
  4. The 12 demo scenarios (illustrative): does the full engine match the expected band?

Every number prints its n and Wilson 95% interval where it is a proportion. The kit never
computes a band: it calls `satyapan.policy` through `pipeline.recompute`. Raw scores are never
printed (oracle-abuse rule). Nothing is sent anywhere; report drafts stay MANUAL_ONLY.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from research.heldout.run_eval import evaluate as heldout_evaluate  # noqa: E402
from research.heldout.stats import (  # noqa: E402
    git_commit,
    load_jsonl,
    sha256_path,
    split_of,
)
from satyapan.asks.extractor import extract_asks  # noqa: E402
from satyapan.asks.phrasebook import extract_live_asks  # noqa: E402
from satyapan.context import strip_context  # noqa: E402
from satyapan.contracts import (  # noqa: E402
    Case,
    CaseKind,
    Channel,
    Evidence,
    PaymentAction,
    PaymentRail,
)
from satyapan.document.checker import document_signals  # noqa: E402
from satyapan.document.extract import extract_invoice_fields  # noqa: E402
from satyapan.document.pdf import extract_pdf_text, read_pdf_metadata  # noqa: E402
from satyapan.email.parser import parse_eml  # noqa: E402
from satyapan.email.signals import email_signals  # noqa: E402
from satyapan.explain.templates import explain_template  # noqa: E402
from satyapan.master import load_master  # noqa: E402
from satyapan.pipeline import (  # noqa: E402
    PipelineContext,
    analyze_evidence,
    merge_output,
    recompute,
)
from satyapan.policy import decide_rules_only  # noqa: E402
from satyapan.repository import CaseRepository  # noqa: E402
from satyapan.settings import Settings  # noqa: E402
from satyapan.voice.rules import VoiceThresholds  # noqa: E402

DEMO = ROOT / "data" / "demo"
HELD = ROOT / "research" / "heldout"
RESULTS = ROOT / "results"
ASK_TYPES = ("A1", "A2", "A3", "A4", "A5", "A6", "A7")

LIMITS = (
    "Synthetic, team/AI-authored data; no real customer, bank or personal data.",
    "No detector was trained on the test split. The lexicon, context filter, phrasebook and "
    "policy are deterministic rules; the split is pre-registered by sha256(id) parity.",
    "The product numbers include the live phrasebook (written from team knowledge, not fitted); "
    "the frozen-lexicon numbers remain the research claim.",
    "E-mail/invoice fixtures are functional checks (n=10 / n=6), not a generalisation estimate.",
    "The 12 demo scenarios are illustrative (n=12); the alert budget is the measured estimate.",
    "We do not claim field accuracy, a prevented-loss figure or media-origin authenticity.",
)


# --------------------------------------------------------------------------- formatting
def pct(w: dict[str, Any]) -> str:
    if w.get("value") is None:
        return "n/a"
    lo, hi = w["ci95"]
    return f"{100 * w['value']:.1f}% [{100 * lo:.1f}-{100 * hi:.1f}] ({w['k']}/{w['n']})"


def rate(w: dict[str, Any]) -> str:
    if w.get("value") is None:
        return "n/a"
    return f"{100 * w['value']:.1f}% ({w['k']}/{w['n']})"


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if hasattr(value, "value"):
        return value.value
    return value


def _identity(text: str) -> str:
    return text


def _with_context(text: str) -> str:
    return strip_context(text).cleaned


# --------------------------------------------------------------------------- 1. ask eval
def ask_scoreboard() -> dict[str, Any]:
    asks = load_jsonl(HELD / "asks_heldout.jsonl")
    benign = load_jsonl(HELD / "benign_ap.jsonl")
    rows = [r for r in asks if split_of(r["id"]) == "test"]
    negs = [r for r in benign if split_of(r["id"]) == "test"]
    configs = {
        "frozen lexicon v1.0": (_identity, extract_asks),
        "context v1.2": (_with_context, extract_asks),
        "product (shipped)": (_with_context, extract_live_asks),
    }
    out: dict[str, Any] = {
        "data": {
            "asks": {"n": len(rows), "sha256": sha256_path(HELD / "asks_heldout.jsonl")},
            "benign": {"n": len(negs), "sha256": sha256_path(HELD / "benign_ap.jsonl")},
            "split": "test (sha256(id) parity; pre-registered)",
        },
        "configs": {},
    }
    pred_product: dict[str, set[str]] = {}
    for name, (pre, extractor) in configs.items():
        result, pred = heldout_evaluate(rows, negs, pre, extractor)
        out["configs"][name] = result
        if name == "product (shipped)":
            pred_product = pred

    misses = [
        {
            "id": r["id"],
            "gold": list(r["asks"]),
            "language": r.get("lang"),
            "text": r["text"][:140],
        }
        for r in rows
        if not pred_product.get(r["id"])
    ]
    false_asks = [
        {
            "id": r["id"],
            "predicted": sorted(pred_product.get(r["id"], set())),
            "category": r.get("category"),
            "text": r["text"][:140],
        }
        for r in negs
        if pred_product.get(r["id"])
    ]
    out["failures"] = {
        "attacks_with_no_ask_detected": {"count": len(misses), "examples": misses[:10]},
        "benign_with_a_false_ask": {"count": len(false_asks), "examples": false_asks[:10]},
    }
    return out


# --------------------------------------------------------------------------- 2. alert budget
def alert_scoreboard() -> dict[str, Any]:
    path = RESULTS / "alert_budget.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    variant = "product" if "product" in report["variants"] else "after"
    split = "test"
    v = report["variants"][variant][split]
    return {
        "source": "results/alert_budget.json",
        "sha256": sha256_path(path),
        "measured_at": report.get("date"),
        "commit": report.get("git_commit"),
        "variant": variant,
        "split": split,
        "routine": {
            "hold": v["routine"]["hold"],
            "ge_verify": v["routine"]["ge_verify"],
            "checker_queue": v["routine"]["checker_queue"],
        },
        "attack": {
            "ge_verify": v["attack"]["ge_verify"],
            "hold": v["attack"]["hold"],
            "above_floor": v["attack"]["above_floor"],
        },
        "by_scenario": {
            name: {
                "n": row["n"],
                "ge_verify": row["ge_verify"],
                "hold": row["hold"],
            }
            for name, row in v["attack_by_scenario"].items()
        },
    }


# --------------------------------------------------------------------------- 3. fixtures
def email_fixtures(master: Any) -> dict[str, Any]:
    expected = json.loads((DEMO / "emails" / "expected.json").read_text(encoding="utf-8"))
    failures: list[dict[str, Any]] = []
    for name in sorted(expected):
        exp = expected[name]
        parsed = parse_eml(
            (DEMO / "emails" / name).read_bytes(),
            trusted_authserv_id=Settings().trusted_authserv_id,
        )
        out = email_signals(parsed, master, f"ev_judge_{name.split('.')[0]}")
        got = sorted(s.code.value for s in out.signals)
        want = sorted(exp["signals"])
        got_grey = sorted(g.value for g in out.grey_reasons)
        want_grey = sorted(exp["grey"])
        if got != want or got_grey != want_grey:
            failures.append(
                {
                    "file": name,
                    "expected_signals": want,
                    "got_signals": got,
                    "expected_grey": want_grey,
                    "got_grey": got_grey,
                }
            )
    return {"n": len(expected), "exact": len(expected) - len(failures), "failures": failures}


def invoice_fixtures(master: Any) -> dict[str, Any]:
    expected = json.loads((DEMO / "invoices" / "expected.json").read_text(encoding="utf-8"))
    failures: list[dict[str, Any]] = []
    for name in sorted(expected):
        exp = expected[name]
        data = (DEMO / "invoices" / name).read_bytes()
        fields = extract_invoice_fields(extract_pdf_text(data))
        meta = read_pdf_metadata(data)
        out = document_signals(fields, meta, master, None, f"ev_judge_{name.split('.')[0]}")
        got = sorted(s.code.value for s in out.signals)
        want = sorted(exp["signals"])
        fields_ok = fields.model_dump(mode="json") == exp["fields"]
        meta_ok = meta.eof_count == exp["eof_count"]
        if got != want or not fields_ok or not meta_ok:
            failures.append(
                {
                    "file": name,
                    "expected_signals": want,
                    "got_signals": got,
                    "fields_ok": fields_ok,
                    "meta_ok": meta_ok,
                }
            )
    return {"n": len(expected), "exact": len(expected) - len(failures), "failures": failures}


# --------------------------------------------------------------------------- 4. demo cases
def demo_scoreboard(master: Any) -> dict[str, Any]:
    repo = CaseRepository.from_fixtures(master, DEMO / "cases")
    expected = json.loads((DEMO / "expected_decisions.json").read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for case in repo.all_cases():
        assert case.decision is not None
        full = case.decision.band.value
        rules = decide_rules_only(case, master).band.value
        rows.append(
            {
                "case": case.id,
                "title": case.title,
                "rules_only": rules,
                "full": full,
                "expected_full": expected[case.id]["full"],
                "match": full == expected[case.id]["full"],
                "changed": rules != full,
            }
        )
    return {
        "n": len(rows),
        "matches": sum(1 for r in rows if r["match"]),
        "changed": sum(1 for r in rows if r["changed"]),
        "rows": rows,
    }


# --------------------------------------------------------------------------- 5. live check
def _channel_for(path: Path | None) -> Channel:
    if path is None:
        return Channel.MANUAL
    suffix = path.suffix.lower()
    if suffix == ".eml":
        return Channel.EMAIL
    if suffix == ".pdf":
        return Channel.PDF
    if suffix in {".wav", ".mp3", ".m4a", ".ogg", ".opus", ".flac"}:
        return Channel.VOICE_NOTE
    if suffix in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
        return Channel.VIDEO
    return Channel.MANUAL


def _payment(
    master: Any,
    *,
    vendor_id: str | None,
    amount: int,
    account: str | None,
    ifsc: str | None,
    beneficiary: str | None,
) -> PaymentAction:
    vendor = master.vendor(vendor_id) if vendor_id else None
    if vendor is not None and account is None and vendor.accounts:
        account = vendor.accounts[0].account_number
        ifsc = ifsc or vendor.accounts[0].ifsc
    beneficiary = beneficiary or (vendor.legal_name if vendor else "Judge Kit Payee")
    return PaymentAction(
        id="txn_judge_kit",
        vendor_id=vendor_id,
        beneficiary_name=beneficiary,
        account_number=account,
        ifsc=ifsc,
        amount_inr=amount,
        rail=PaymentRail.NEFT,
        created_by="emp_priya",
        created_at=datetime.now(UTC),
    )


def live_check(args: argparse.Namespace) -> int:
    master = load_master(Settings().data_dir)
    if args.text is not None:
        raw = args.text.encode("utf-8")
        source = "text"
        channel = Channel.MANUAL
        filename = None
    else:
        path = Path(args.file).expanduser()
        if not path.is_file():
            print(f"file not found: {path}")
            return 2
        raw = path.read_bytes()
        source = path.name
        channel = _channel_for(path)
        filename = path.name
    evidence = Evidence(
        id="ev_judge_kit",
        case_id="case_judge_kit",
        channel=channel,
        filename=filename,
        media_type="application/octet-stream",
        sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
        captured_at=datetime.now(UTC),
        submitted_by="emp_priya",
        storage_uri="mem://judge_kit",
        excerpt=raw[:200].decode("utf-8", errors="replace") if channel == Channel.MANUAL else None,
    )
    txn = _payment(
        master,
        vendor_id=None if args.new_payee else args.vendor_id,
        amount=args.amount,
        account=args.account,
        ifsc=args.ifsc,
        beneficiary=args.beneficiary,
    )
    case = Case(
        id="case_judge_kit",
        title=f"Judge kit: {source}",
        kind=CaseKind.PAYMENT,
        created_at=datetime.now(UTC),
        created_by="emp_priya",
        txn=txn,
        evidence=[evidence],
    )
    ctx = PipelineContext(
        master=master,
        settings=Settings(),
        thresholds=VoiceThresholds(tau_hi=0.9, tau_lo=0.6, model_version="unused"),
        live_phrasebook=True,
    )
    out = analyze_evidence(raw, evidence, case, ctx)
    case = recompute(merge_output(case, evidence, out), master)
    assert case.decision is not None
    decision = case.decision

    print("=" * 78)
    print("SATYAPAN JUDGE KIT — live check")
    print("=" * 78)
    print(f"Input       : {source} ({channel.value}, {len(raw):,} bytes)")
    payee = "NEW / changed beneficiary" if txn.vendor_id is None else f"vendor {txn.vendor_id}"
    masked = f"••••{txn.account_number[-4:]}" if txn.account_number else (txn.upi_id or "n/a")
    print(f"Payment     : Rs {txn.amount_inr:,} to {masked} ({txn.ifsc or 'n/a'}), {payee}")
    print(f"Detector    : {out.detector} v{out.version}")
    if out.grey_reasons:
        print(f"Grey        : {', '.join(g.value for g in out.grey_reasons)} (never PASS)")
    if out.error:
        print(f"When parsing : {out.error}")
    print()
    print("Signals (evidence can only raise the band):")
    if not out.signals:
        print("  (none)")
    for signal in out.signals:
        print(f"  {signal.code.value:<34} {signal.source.value:<14} {signal.detector}")
    if out.artifacts.get("asks"):
        print()
        print("Asks detected:")
        for ask in out.artifacts["asks"][:6]:
            print(f"  {ask['ask_type']}: “{ask['text']}”")
    if out.artifacts.get("context"):
        removed = out.artifacts["context"].get("removed", [])
        if removed:
            print(
                f"Context ignored: {len(removed)} line(s) (footers / warnings), kept in artifacts"
            )
    print()
    print("Policy (the only component allowed to set a band):")
    print(f"  Floor band : {decision.floor_band.value}  (trusted payment + vendor master only)")
    print(f"  Final band : {decision.band.value}")
    print(f"  Action     : {decision.action_type.value}   Queue: {decision.queue.value}")
    print(f"  Grey       : {decision.grey}")
    print(f"  Reasons    : {', '.join(r.value for r in decision.reason_codes) or '(none)'}")
    if decision.info_codes:
        print(f"  Info       : {', '.join(r.value for r in decision.info_codes)}")
    print()
    print(explain_template(decision, "en").text)  # type: ignore[arg-type]
    print()
    print("Safeguards: no raw score is shown; nothing was sent; report drafts are MANUAL_ONLY.")
    print("=" * 78)
    return 0


def screen_check(text: str) -> int:
    from satyapan.api.state import AppState

    state = AppState.build(Settings())
    finding = state.companion().check_text(text, app=None, source="judge_kit")
    print("=" * 78)
    print("SATYAPAN JUDGE KIT — screen / clipboard finding (no band is set here)")
    print("=" * 78)
    print(f"Suspicious       : {finding.suspicious}")
    print("Asks             : " + (", ".join(q.code for q in finding.asks) or "(none)"))
    print("Cues             : " + (", ".join(finding.cues) or "(none)"))
    print("Accounts seen    : " + (", ".join(finding.accounts_masked) or "(none)"))
    print("Unknown accounts : " + (", ".join(finding.unknown_accounts_masked) or "(none)"))
    print("Vendors named    : " + (", ".join(finding.vendors) or "(none)"))
    print()
    print("This is an informational card. The text becomes evidence only if the user says")
    print("'Check it properly'; then satyapan.policy decides, exactly as in the live check.")
    print("=" * 78)
    return 0


# --------------------------------------------------------------------------- scoreboard
def print_scoreboard(report: dict[str, Any]) -> None:
    print("=" * 84)
    print("SATYAPAN JUDGE KIT — measured scoreboard (local, no network, fake data)")
    print("=" * 84)
    print(f"commit {report['git_commit']} | {report['date']} | {report['runtime_s']:.2f}s")
    print()

    asks = report["ask"]
    print("1) ASK DETECTION — pre-registered held-out TEST split")
    n_attack = asks["data"]["asks"]["n"]
    n_benign = asks["data"]["benign"]["n"]
    print(f"   {n_attack} attack texts / {n_benign} benign AP texts")
    header = (
        f"   {'configuration':<24} {'precision':<26} {'recall':<26} "
        "attack>=1 ask   benign false ask"
    )
    print(header)
    for name, r in asks["configs"].items():
        print(
            f"   {name:<24} {pct(r['micro']['precision']):<26} "
            f"{pct(r['micro']['recall']):<26} "
            f"{rate(r['attack_any_detected']):<15} {rate(r['benign_false_ask_rate'])}"
        )
    print("   (frozen = research claim; product = shipped context filter + live phrasebook)")
    misses = asks["failures"]["attacks_with_no_ask_detected"]
    false_asks = asks["failures"]["benign_with_a_false_ask"]
    print(
        f"   Failure cases: {misses['count']} attacks got no ask; "
        f"{false_asks['count']} benign texts got one."
    )
    for row in misses["examples"][:3]:
        print(f"     miss {row['id']} gold={row['gold']}: {row['text'][:90]!r}")
    for row in false_asks["examples"][:3]:
        print(
            f"     false {row['id']} {row['predicted']} [{row['category']}]: {row['text'][:90]!r}"
        )
    print()

    ab = report["alert"]
    print(f"2) END-TO-END POLICY — alert budget ({ab['variant']} config, {ab['split']} split)")
    print(f"   Routine payments at HOLD (false alarms): {rate(ab['routine']['hold'])}")
    print(f"   Routine escalated to >= VERIFY        : {rate(ab['routine']['ge_verify'])}")
    print(f"   Attacks at >= VERIFY                  : {rate(ab['attack']['ge_verify'])}")
    print(f"   Attacks at HOLD                       : {rate(ab['attack']['hold'])}")
    print("   Attack catch by scenario (>= VERIFY):")
    for name, row in ab["by_scenario"].items():
        print(f"     {name:<38} {rate(row['ge_verify'])}")
    print(
        f"   Source: {ab['source']} (sha256 {ab['sha256'][:12]}..., measured {ab['measured_at']})"
    )
    print()

    email = report["email"]
    invoice = report["invoice"]
    print("3) COMMUNICATION CHECKERS — labelled fixtures (functional, not a generalisation claim)")
    print(f"   E-mail signals exact match: {email['exact']}/{email['n']}")
    print(f"   Invoice signals + fields + metadata: {invoice['exact']}/{invoice['n']}")
    for row in email["failures"] + invoice["failures"]:
        print(f"     MISMATCH {row}")
    print()

    demo = report["demo"]
    print("4) DEMO SCENARIOS (illustrative, n=12) — full engine vs expected band")
    print(f"   Bands match expected: {demo['matches']}/{demo['n']}")
    print(f"   Detectors changed the rules-only outcome: {demo['changed']}/{demo['n']}")
    print()

    print("5) SAFEGUARDS (running code, not slides)")
    print("   band set only by satyapan.policy; evidence raises, never lowers")
    print("   no raw scores to makers; OOB contact from the directory only")
    print("   no auto-submit: report drafts are MANUAL_ONLY; a human presses Submit")
    print("   full proof: make check (property-tested invariants in tests/invariants/)")
    print()
    print("LIMITS")
    for line in LIMITS:
        print(f"  - {line}")
    print("=" * 84)


def build_report() -> dict[str, Any]:
    started = time.perf_counter()
    master = load_master(Settings().data_dir)
    report: dict[str, Any] = {
        "what": "Judge kit scoreboard (held-out ask detection, alert budget, fixtures, demo)",
        "date": datetime.now(UTC).date().isoformat(),
        "git_commit": git_commit(),
        "ask": ask_scoreboard(),
        "alert": alert_scoreboard(),
        "email": email_fixtures(master),
        "invoice": invoice_fixtures(master),
        "demo": demo_scoreboard(master),
        "limits": list(LIMITS),
    }
    report["runtime_s"] = round(time.perf_counter() - started, 2)
    return report


def write_report(report: dict[str, Any]) -> None:
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "judge_kit.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# Judge kit — measured scoreboard",
        "",
        f"Generated by `uv run python scripts/judge_kit.py` at commit `{report['git_commit']}` "
        f"on {report['date']} in {report['runtime_s']}s.",
        "",
        "## 1. Ask detection (pre-registered held-out test split)",
        "",
        "| Configuration | Precision | Recall | Attack >= 1 ask | Benign false ask |",
        "|---|---|---|---|---|",
    ]
    for name, r in report["ask"]["configs"].items():
        lines.append(
            f"| {name} | {pct(r['micro']['precision'])} | {pct(r['micro']['recall'])} | "
            f"{rate(r['attack_any_detected'])} | {rate(r['benign_false_ask_rate'])} |"
        )
    ab = report["alert"]
    lines += [
        "",
        "## 2. End-to-end policy (alert budget)",
        "",
        f"Variant `{ab['variant']}`, split `{ab['split']}`, measured {ab['measured_at']}.",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Routine payments at HOLD | {rate(ab['routine']['hold'])} |",
        f"| Routine escalated to >= VERIFY | {rate(ab['routine']['ge_verify'])} |",
        f"| Attacks at >= VERIFY | {rate(ab['attack']['ge_verify'])} |",
        f"| Attacks at HOLD | {rate(ab['attack']['hold'])} |",
        "",
        "| Attack scenario | n | >= VERIFY | HOLD |",
        "|---|---|---|---|",
    ]
    for name, row in ab["by_scenario"].items():
        lines.append(f"| {name} | {row['n']} | {rate(row['ge_verify'])} | {rate(row['hold'])} |")
    lines += [
        "",
        "## 3. Communication checkers (labelled fixtures)",
        "",
        f"- E-mail signals exact match: **{report['email']['exact']}/{report['email']['n']}**",
        f"- Invoice signals + fields + metadata: "
        f"**{report['invoice']['exact']}/{report['invoice']['n']}**",
        "",
        "## 4. Demo scenarios (illustrative, n=12)",
        "",
        f"- Bands match expected: **{report['demo']['matches']}/{report['demo']['n']}**",
        f"- Detectors changed the rules-only outcome: "
        f"**{report['demo']['changed']}/{report['demo']['n']}**",
        "",
        "## Limits",
        "",
        *[f"- {line}" for line in LIMITS],
        "",
    ]
    (RESULTS / "judge_kit.md").write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------- CLI
def main() -> None:
    parser = argparse.ArgumentParser(description="Satyapan judge kit")
    parser.add_argument("--text", help="check this text (email body, call transcript, screen)")
    parser.add_argument("--file", help="check this file (.eml, .pdf, audio, video, text)")
    parser.add_argument("--screen", action="store_true", help="screen/clipboard finding (no band)")
    parser.add_argument("--vendor-id", default="V001", help="known vendor id (default V001)")
    parser.add_argument("--new-payee", action="store_true", help="treat the payment as a new payee")
    parser.add_argument("--amount", type=int, default=210_000, help="payment amount in rupees")
    parser.add_argument("--account", help="beneficiary account (fake data only)")
    parser.add_argument("--ifsc", help="beneficiary IFSC (fake data only)")
    parser.add_argument("--beneficiary", help="beneficiary name")
    parser.add_argument("--json", action="store_true", help="print the scoreboard as JSON")
    args = parser.parse_args()

    if args.screen:
        if args.text is None:
            parser.error("--screen needs --text")
        raise SystemExit(screen_check(args.text))
    if args.text is not None or args.file is not None:
        if args.account is None and args.ifsc is None and args.new_payee:
            args.account, args.ifsc = "9999000099917", "FAKE0009999"
        raise SystemExit(live_check(args))

    report = build_report()
    write_report(report)
    if args.json:
        print(json.dumps(report, indent=1, ensure_ascii=False))
    else:
        print_scoreboard(report)
        print(f"wrote {RESULTS / 'judge_kit.json'} and {RESULTS / 'judge_kit.md'}")


if __name__ == "__main__":
    main()
