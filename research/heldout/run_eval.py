"""Measure the FROZEN ask extractor (lexicon v1.0) on the lexicon-blind held-out set.

    uv run python -m research.heldout.run_eval            # writes results/asks_heldout_eval.json

Data: research/heldout/asks_heldout.jsonl (172 attacker asks, multi-label A1-A7) and
research/heldout/benign_ap.jsonl (325 benign AP texts). See research/heldout/README.md for who
wrote them, the label rules and the pre-registered dev/test split.

Variants (same frozen lexicon, only the text fed to it differs):
  - "frozen":  extract_asks(text)                       -- the lexicon as shipped (T05)
  - "context": extract_asks(strip_context(text).cleaned) -- with the leader-owned
               boilerplate/warning layer (src/satyapan/context/), if present.
The "context" layer was designed while looking at the DEV split only. Quote TEST numbers.

Metrics (all with Wilson 95% intervals):
  - per ask type: precision over every text (asks + benign), recall over texts labelled with it
  - micro precision / recall, per language (en / hi-Latn / hi-Deva)
  - attack-level: share of attack texts with >= 1 ask detected, and with ALL gold asks detected
  - benign false-ask rate: share of benign texts with >= 1 ask detected (overall, per category,
    per ask type, and without the 6 'borderline' rows)
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from research.heldout.stats import ROOT, git_commit, load_jsonl, sha256_path, split_of, wilson
from satyapan.asks.extractor import extract_asks
from satyapan.asks.lexicon import LEXICON_VERSION

HERE = Path(__file__).resolve().parent
ASKS_PATH = HERE / "asks_heldout.jsonl"
BENIGN_PATH = HERE / "benign_ap.jsonl"
OUT_PATH = ROOT / "results" / "asks_heldout_eval.json"
ASK_TYPES = ["A1", "A2", "A3", "A4", "A5", "A6", "A7"]
LANGS = ["en", "hi-Latn", "hi-Deva"]


def predict(text: str, pre: Callable[[str], str]) -> set[str]:
    return {s.ask_type.value for s in extract_asks(pre(text))}


def _identity(text: str) -> str:
    return text


def _context(text: str) -> str:
    from satyapan.context.boilerplate import strip_context

    return strip_context(text).cleaned


def evaluate(rows: list[dict[str, Any]], benign: list[dict[str, Any]], pre: Callable[[str], str]):
    pred = {r["id"]: predict(r["text"], pre) for r in [*rows, *benign]}
    every = [*rows, *benign]

    def pr(subset_asks: list[dict[str, Any]], subset_all: list[dict[str, Any]], a: str | None):
        types = [a] if a else ASK_TYPES
        tp = sum(1 for r in subset_all for t in types if t in r["asks"] and t in pred[r["id"]])
        fp = sum(1 for r in subset_all for t in types if t not in r["asks"] and t in pred[r["id"]])
        fn = sum(1 for r in subset_asks for t in types if t in r["asks"] and t not in pred[r["id"]])
        return {"precision": wilson(tp, tp + fp), "recall": wilson(tp, tp + fn)}

    out: dict[str, Any] = {
        "per_ask": {a: pr(rows, every, a) for a in ASK_TYPES},
        "micro": pr(rows, every, None),
        "per_language": {},
    }
    for lang in LANGS:
        la = [r for r in rows if r["lang"] == lang]
        lb = [r for r in benign if r["lang"] == lang]
        out["per_language"][lang] = {
            "micro": pr(la, [*la, *lb], None),
            "recall_per_ask": {a: pr(la, la, a)["recall"] for a in ASK_TYPES},
            "attack_any_detected": wilson(sum(1 for r in la if pred[r["id"]]), len(la)),
            "benign_false_ask_rate": wilson(sum(1 for r in lb if pred[r["id"]]), len(lb)),
        }
    out["attack_any_detected"] = wilson(sum(1 for r in rows if pred[r["id"]]), len(rows))
    out["attack_all_gold_detected"] = wilson(
        sum(1 for r in rows if set(r["asks"]) <= pred[r["id"]]), len(rows)
    )
    flagged = [r for r in benign if pred[r["id"]]]
    out["benign_false_ask_rate"] = wilson(len(flagged), len(benign))
    clean = [r for r in benign if not r.get("borderline")]
    out["benign_false_ask_rate_excl_borderline"] = wilson(
        sum(1 for r in clean if pred[r["id"]]), len(clean)
    )
    cats = sorted({r["category"] for r in benign})
    out["benign_false_ask_rate_by_category"] = {
        c: wilson(
            sum(1 for r in benign if r["category"] == c and pred[r["id"]]),
            sum(1 for r in benign if r["category"] == c),
        )
        for c in cats
    }
    out["benign_false_asks_by_type"] = {
        a: sum(1 for r in benign if a in pred[r["id"]]) for a in ASK_TYPES
    }
    return out, pred


def main() -> None:
    asks = load_jsonl(ASKS_PATH)
    benign = load_jsonl(BENIGN_PATH)
    variants: dict[str, Callable[[str], str]] = {"frozen": _identity}
    try:
        import satyapan.context.boilerplate  # noqa: F401

        variants["context"] = _context
    except ImportError:
        pass

    report: dict[str, Any] = {
        "what": "Frozen ask extractor on a lexicon-blind held-out set (synthetic, AI-written)",
        "date": date.today().isoformat(),
        "git_commit": git_commit(),
        "lexicon_version": LEXICON_VERSION,
        "command": "uv run python -m research.heldout.run_eval",
        "data": {
            "asks_heldout.jsonl": {"n": len(asks), "sha256": sha256_path(ASKS_PATH)},
            "benign_ap.jsonl": {"n": len(benign), "sha256": sha256_path(BENIGN_PATH)},
            "source": "synthetic; written by an AI agent before it opened the lexicon "
            "(research/heldout/README.md)",
        },
        "split_rule": "dev if sha256(id) is even else test; context layer tuned on dev only",
        "variants": {},
    }
    examples: dict[str, Any] = {}
    for name, pre in variants.items():
        report["variants"][name] = {}
        for split in ("all", "dev", "test"):
            a = [r for r in asks if split == "all" or split_of(r["id"]) == split]
            b = [r for r in benign if split == "all" or split_of(r["id"]) == split]
            res, pred = evaluate(a, b, pre)
            report["variants"][name][split] = res
            if split == "dev":  # examples only from DEV (never browse test rows while tuning)
                examples[name] = {
                    "dev_benign_flagged": [
                        {"id": r["id"], "pred": sorted(pred[r["id"]])} for r in b if pred[r["id"]]
                    ][:40],
                    "dev_asks_missed": [
                        {"id": r["id"], "gold": r["asks"], "pred": sorted(pred[r["id"]])}
                        for r in a
                        if not set(r["asks"]) <= pred[r["id"]]
                    ][:40],
                }
    report["dev_examples"] = examples
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for name in report["variants"]:
        for split in ("all", "test"):
            r = report["variants"][name][split]
            print(
                f"{name:8s} {split:4s} P={r['micro']['precision']['value']} "
                f"R={r['micro']['recall']['value']} any={r['attack_any_detected']['value']} "
                f"benignFA={r['benign_false_ask_rate']['value']} "
                f"(n_ben={r['benign_false_ask_rate']['n']})"
            )


if __name__ == "__main__":
    main()
