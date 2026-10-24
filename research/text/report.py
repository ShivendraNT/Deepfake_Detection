"""Render results/text_benchmark.json as Markdown (results/text_benchmark.md)."""

from __future__ import annotations

from typing import Any

MODELS = ("tfidf_union", "tfidf_spec", "tfidf_lodo", "asks_product", "asks_frozen")


def _ci(x: dict[str, Any] | None) -> str:
    if not x:
        return "n/a"
    return f"{x['value']:.3f} [{x['low']:.3f}, {x['high']:.3f}]"


def _rate(w: dict[str, Any] | None) -> str:
    if not w or w.get("value") is None:
        return "n/a"
    lo, hi = w["ci95"]
    return f"{100 * w['value']:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]"


def render(r: dict[str, Any]) -> str:
    u = r["union"]
    out = [
        "# Text benchmark: scam / phishing / fraud messages (research/text/bench.py)",
        "",
        "Open datasets, template-deduplicated, leakage-safe splits; C chosen by 5-fold "
        "GroupKFold CV on train; thresholds frozen on val (tau_hi = 1% FPR on legitimate val "
        "texts); every test split scored once. AUC/AP: 95% template-cluster bootstrap; rates: "
        "Wilson 95%. Protocol: docs/TEXT_BENCHMARK.md.",
        "",
        f"Shipped model (tfidf_union): C = {u['cv']['best_C']}, CV AUC "
        f"{u['cv']['cv_auc_mean']} ± {u['cv']['cv_auc_sd']}; tau_hi = "
        f"{u['thresholds']['tau_hi']:.4f}.",
        "",
        "## Test AUC per dataset",
        "",
        "| Dataset | n (fraud) | " + " | ".join(MODELS) + " |",
        "|---|---|" + "---|" * len(MODELS),
    ]
    for name, block in r["per_dataset"].items():
        n = block["tfidf_union"]
        cells = [_ci(block[m].get("auc")) for m in MODELS]
        out.append(f"| {name} | {n['n']} ({n['n_fraud']}) | " + " | ".join(cells) + " |")
    out += [
        "",
        "## Operating point of the shipped model (threshold frozen on val, 1% FPR target)",
        "",
        "| Dataset | caught (TPR) | false alarms (FPR) | F1 at val max-F1 thr |",
        "|---|---|---|---|",
    ]
    for name, block in r["per_dataset"].items():
        b = block["tfidf_union"]
        out.append(
            f"| {name} | {_rate(b.get('tpr@tau_hi'))} | {_rate(b.get('fpr@tau_hi'))} | "
            f"{b.get('f1@tau_f1', 'n/a')} |"
        )
    out += [
        "",
        "## Zero-shot ask lexicon (>= 1 ask = flag)",
        "",
        "| Dataset | asks_product TPR | asks_product FPR | asks_frozen TPR | asks_frozen FPR |",
        "|---|---|---|---|---|",
    ]
    for name, block in r["per_dataset"].items():
        a, f = block["asks_product"], block["asks_frozen"]
        out.append(
            f"| {name} | {_rate(a.get('tpr@tau_hi'))} | {_rate(a.get('fpr@tau_hi'))} | "
            f"{_rate(f.get('tpr@tau_hi'))} | {_rate(f.get('fpr@tau_hi'))} |"
        )
    rob = r["robustness"]
    out += [
        "",
        f"## Evasion robustness ({rob['n_fraud']} fraud test texts attacked; "
        f"{rob['n_legit']} clean legitimate texts)",
        "",
        "| Attack | TPR @ tau_hi, with de-obfuscation | TPR, without | AUC with | AUC without |"
        " asks_product TPR |",
        "|---|---|---|---|---|---|",
    ]
    for kind, row in rob.items():
        if not isinstance(row, dict) or "raw" not in row:
            continue
        d, w = row["deobfuscated"], row["raw"]
        out.append(
            f"| {kind} | {_rate(d['tpr@tau_hi'])} | {_rate(w['tpr@tau_hi'])} | "
            f"{d['auc']} | {w['auc']} | {_rate(row['asks_product_tpr'])} |"
        )
    return "\n".join(out) + "\n"
