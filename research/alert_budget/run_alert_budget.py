"""Alert budget: how many ROUTINE payments get escalated, and how many ATTACKS are caught?

    uv run python -m research.alert_budget.run_alert_budget
    -> results/alert_budget.json + results/alert_budget.md

Every case goes through the REAL decision path: satyapan.pipeline.analyze_evidence() runs the
real (frozen) ask extractor on the message text, merge_output() adds its signals, recompute()
calls satyapan.policy.decide(). No signal is hand-set.

Cases (research/alert_budget/synth.py, deterministic, synthetic):
  - routine: 400 known-vendor payments (floor K1) with 1-3 benign AP messages each, drawn from
    research/heldout/benign_ap.jsonl (200 cases use dev-split texts, 200 test-split texts).
  - attack: one case per held-out attacker ask (172) shaped by the ask (payee change, new
    payee, small new payee, credential/remote-access request), plus 12 de-minimis splitting
    cases (no message).

Variants (only what is available in the code being measured is run):
  - before:       no context layer, no corroboration rule, no 30-day de-minimis window
  - context_only: context layer on, old policy
  - policy_only:  new policy (corroboration + 30-day window), no context layer
  - after:        both (the shipped defaults)
Emails are fed as text (Channel.MANUAL): the .eml parser and sender checks (T03/T04) are not
built, so no sender-auth signals exist in this benchmark for routine or attack cases.
"""

from __future__ import annotations

import dataclasses
import json
from collections import Counter
from datetime import date
from typing import Any

from research.alert_budget.synth import (
    SynthCase,
    as_of,
    attack_cases,
    build_master,
    routine_cases,
    splitting_cases,
)
from research.heldout.stats import ROOT, git_commit, load_jsonl, sha256_path, wilson
from satyapan.contracts import Band, Case
from satyapan.master.store import MasterData
from satyapan.pipeline import PipelineContext, analyze_evidence, merge_output, recompute
from satyapan.policy.bands import rank
from satyapan.policy.config import PolicyConfig
from satyapan.settings import Settings
from satyapan.voice.rules import VoiceThresholds

HELD = ROOT / "research" / "heldout"
OUT_JSON = ROOT / "results" / "alert_budget.json"
OUT_MD = ROOT / "results" / "alert_budget.md"

VARIANTS: dict[str, dict[str, Any]] = {
    "before": {"context": False, "cfg": {"ask_corroboration": False, "de_minimis_window_days": 0}},
    "context_only": {
        "context": True,
        "cfg": {"ask_corroboration": False, "de_minimis_window_days": 0},
    },
    "policy_only": {"context": False, "cfg": {}},
    "after": {"context": True, "cfg": {}},
}


def _fields(cls: type) -> set[str]:
    return {f.name for f in dataclasses.fields(cls)}


def available(name: str) -> bool:
    """Pre-fix code has none of the new knobs: then only 'before' (= its defaults) can run."""
    return name == "before" or "ask_corroboration" in _fields(PolicyConfig)


def _master_for(sc: SynthCase, base: MasterData) -> MasterData:
    if not sc.prior_new_payee_payments or not hasattr(base, "new_payee_payments"):
        return base
    from satyapan.contracts.master import OutgoingPayment  # added with the 30-day window

    rows = [
        OutgoingPayment(**{**p, "paid_on": as_of(p["paid_on"])})
        for p in sc.prior_new_payee_payments
    ]
    return dataclasses.replace(base, new_payee_payments=rows)


def run_case(sc: SynthCase, master: MasterData, variant: dict[str, Any]) -> Case:
    cfg_kwargs = {k: v for k, v in variant["cfg"].items() if k in _fields(PolicyConfig)}
    cfg = PolicyConfig(**cfg_kwargs)
    ctx_kwargs: dict[str, Any] = {}
    if "context_filter" in _fields(PipelineContext):
        ctx_kwargs["context_filter"] = variant["context"]
    m = _master_for(sc, master)
    ctx = PipelineContext(
        master=m,
        settings=Settings(),
        thresholds=VoiceThresholds(tau_hi=0.9, tau_lo=0.6, model_version="unused"),
        **ctx_kwargs,
    )
    case = sc.case
    for ev, data in zip(sc.case.evidence, sc.payloads, strict=True):
        case = merge_output(case, ev, analyze_evidence(data, ev, case, ctx))
    return recompute(case, m, cfg)


def summarise(rows: list[tuple[SynthCase, Case]]) -> dict[str, Any]:
    n = len(rows)
    bands = [c.decision.band for _, c in rows if c.decision]
    floors = [c.decision.floor_band for _, c in rows if c.decision]
    ge_verify = sum(1 for b in bands if rank(b) >= rank(Band.VERIFY))
    hold = sum(1 for b in bands if b == Band.HOLD)
    above_floor = sum(1 for b, f in zip(bands, floors, strict=True) if rank(b) > rank(f))
    checker = sum(1 for _, c in rows if c.queue.value == "CHECKER_REVIEW")
    raising: Counter[str] = Counter()
    hold_reasons: Counter[str] = Counter()
    for _, c in rows:
        assert c.decision is not None
        codes = [r.value for r in c.decision.reason_codes if not r.value.startswith("FLOOR_")]
        raising.update(set(codes))
        if c.decision.band == Band.HOLD:
            hold_reasons.update(set(codes))
    return {
        "n": n,
        "ge_verify": wilson(ge_verify, n),
        "verify_exactly": wilson(ge_verify - hold, n),
        "hold": wilson(hold, n),
        "above_floor": wilson(above_floor, n),
        "checker_queue": wilson(checker, n),
        "cases_with_reason_code": dict(raising.most_common()),
        "hold_cases_with_reason_code": dict(hold_reasons.most_common()),
    }


def main() -> None:
    asks = load_jsonl(HELD / "asks_heldout.jsonl")
    benign = load_jsonl(HELD / "benign_ap.jsonl")
    master = build_master()
    cases = [*routine_cases(benign), *attack_cases(asks, benign), *splitting_cases()]

    previous: dict[str, Any] = {}
    if OUT_JSON.exists():
        previous = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    pre_fix = "ask_corroboration" not in _fields(PolicyConfig)

    report: dict[str, Any] = {
        "what": "Alert budget through the real pipeline (synthetic cases)",
        "date": date.today().isoformat(),
        "git_commit": git_commit(),
        "code_state": "pre-fix (policy 1.0.0, no context layer)" if pre_fix else "post-fix",
        "command": "uv run python -m research.alert_budget.run_alert_budget",
        "data": {
            "benign_ap.jsonl_sha256": sha256_path(HELD / "benign_ap.jsonl"),
            "asks_heldout.jsonl_sha256": sha256_path(HELD / "asks_heldout.jsonl"),
            "n_routine": sum(1 for c in cases if c.group == "routine"),
            "n_attack": sum(1 for c in cases if c.group == "attack"),
            "source": "synthetic (research/alert_budget/synth.py, research/heldout/)",
        },
        "variants": {},
    }
    for name, variant in VARIANTS.items():
        if not available(name):
            continue
        results = [(sc, run_case(sc, master, variant)) for sc in cases]
        per: dict[str, Any] = {}
        for split in ("all", "dev", "test"):
            sel = [(s, c) for s, c in results if split == "all" or s.split == split]
            per[split] = {
                "routine": summarise([(s, c) for s, c in sel if s.group == "routine"]),
                "attack": summarise([(s, c) for s, c in sel if s.group == "attack"]),
                "attack_by_scenario": {
                    scen: summarise([(s, c) for s, c in sel if s.scenario == scen])
                    for scen in sorted({s.scenario for s, _ in sel if s.group == "attack"})
                },
            }
        report["variants"][name] = per

    if pre_fix:
        report["before_measured_on_pre_fix_code"] = {
            "git_commit": report["git_commit"],
            "result": report["variants"]["before"],
        }
    elif "before_measured_on_pre_fix_code" in previous:
        pf = previous["before_measured_on_pre_fix_code"]
        report["before_measured_on_pre_fix_code"] = pf
        report["before_emulation_matches_pre_fix_code"] = _same(
            pf["result"], report["variants"]["before"]
        )

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_md(report), encoding="utf-8")
    print(render_md(report))


def _same(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Compare band outcomes only (counts), ignoring float formatting differences."""
    keys = ("ge_verify", "hold", "checker_queue")
    for split in ("all", "dev", "test"):
        for grp in ("routine",):
            for k in keys:
                if a[split][grp][k]["k"] != b[split][grp][k]["k"]:
                    return False
        for k in keys:
            ka = a[split]["attack"][k]["k"]
            kb = b[split]["attack"][k]["k"]
            if ka != kb:
                return False
    return True


def _pct(w: dict[str, Any]) -> str:
    if w["value"] is None:
        return "n/a"
    lo, hi = w["ci95"]
    return f"{100 * w['value']:.1f}% [{100 * lo:.1f}-{100 * hi:.1f}] ({w['k']}/{w['n']})"


def render_md(r: dict[str, Any]) -> str:
    v = r["variants"]
    names = list(v)
    out = [
        "# Alert budget (synthetic, real decision path)",
        "",
        f"Generated by `{r['command']}` at commit `{r['git_commit']}` on {r['date']}. "
        f"Code state: {r['code_state']}.",
        "",
        "Routine = known vendor, registered account, in-pattern amount (floor PASS), with 1-3 "
        "realistic benign AP messages (footers, bank OTP SMS, IT notices, Diwali vouchers, "
        "GST/TDS mails, WhatsApp chatter). Attack = one case per held-out attacker ask "
        "(payee change, new payee, credential/remote-access request) + 12 de-minimis "
        "splitting cases. Signals come only from the real ask extractor run on the text; "
        "e-mail header checks (T03/T04) are not built, so they contribute nothing here.",
        "",
        "Every routine case carries at least one message and the benign set is deliberately "
        "rich in footers and bank SMS, so routine rates are an upper bound for a real "
        "payment run. 95% Wilson intervals in brackets. **Quote the `test` split**: the "
        "context layer was designed while reading dev-split texts only.",
        "",
    ]
    for split in ("test", "all"):
        out += [f"## Split: {split}", ""]
        out += ["| Metric | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
        rows = [
            ("Routine escalated to >= VERIFY", "routine", "ge_verify"),
            ("Routine at HOLD", "routine", "hold"),
            ("Routine sent to checker queue", "routine", "checker_queue"),
            ("Attack at >= VERIFY", "attack", "ge_verify"),
            ("Attack at HOLD", "attack", "hold"),
            ("Attack raised above its floor by detectors", "attack", "above_floor"),
        ]
        for label, grp, key in rows:
            out.append(
                f"| {label} | " + " | ".join(_pct(v[n][split][grp][key]) for n in names) + " |"
            )
        out += ["", "Attack catch by scenario (>= VERIFY / HOLD):", ""]
        out += ["| Scenario | n | " + " | ".join(names) + " |", "|---|---|" + "---|" * len(names)]
        for scen, s in v[names[0]][split]["attack_by_scenario"].items():
            cells = []
            for n in names:
                x = v[n][split]["attack_by_scenario"][scen]
                cells.append(
                    f"{100 * (x['ge_verify']['value'] or 0):.0f}% / "
                    f"{100 * (x['hold']['value'] or 0):.0f}%"
                )
            out.append(f"| {scen} | {s['n']} | " + " | ".join(cells) + " |")
        out += ["", "Routine cases per raising reason code (a case can have several):", ""]
        codes = sorted({c for n in names for c in v[n][split]["routine"]["cases_with_reason_code"]})
        out += ["| Reason code | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
        for code in codes:
            out.append(
                f"| {code} | "
                + " | ".join(
                    str(v[n][split]["routine"]["cases_with_reason_code"].get(code, 0))
                    for n in names
                )
                + " |"
            )
        out.append("")
    if "before_emulation_matches_pre_fix_code" in r:
        pf = r["before_measured_on_pre_fix_code"]["git_commit"]
        out.append(
            f"The `before` column is produced by switching the new knobs off. It was also "
            f"measured on the unmodified pre-fix code (commit `{pf}`); band counts match: "
            f"**{r['before_emulation_matches_pre_fix_code']}**."
        )
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    main()
