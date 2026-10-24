"""The whole consumer path on open data: what a person gets back from the Scam Check page.

    python -m research.text.consumer_eval     # -> results/consumer_text_eval.{json,md}

The text benchmark (bench.py) measures the scam-text model alone. A person pasting a message
gets more than that: the quick check (text model + asks, band from the policy engine) and the
T24 impossible-claim rules, higher band wins (satyapan.citizen.check). This script sends every
held-out TEST text of the seven open sets through exactly that path and counts the answers.
Nothing is fitted here; the model, thresholds, lexicon and rules are the shipped ones.

"Flagged" = VERIFY or HOLD (the person is told to call back before acting). Texts are cut to
the first 20,000 characters (a long e-mail's body; the page itself takes up to 5,000).
"""

from __future__ import annotations

import json
import time

import pandas as pd

from research.text.data import DATA, ROOT
from research.video.stats import wilson
from satyapan.citizen.rules import scam_check
from satyapan.contracts.enums import Band, Lang
from satyapan.policy.bands import rank

MAX_CHARS = 20_000
LANG_GROUP = {"en": "English", "English": "English", "Hinglish": "Hinglish",
              "hinglish": "Hinglish", "en/hi": "English/Hindi SMS", "Hindi": "Hindi"}  # fmt: skip
FLAG = (Band.VERIFY, Band.HOLD)


def answers(state, texts: list[str]) -> pd.DataFrame:
    from satyapan.quickcheck import quick_check

    rows = []
    for text in texts:
        t = text[:MAX_CHARS]
        policy = quick_check(state, t.encode("utf-8"), "message.txt", "text/plain", Lang.EN).band
        rules = scam_check(t, Lang.EN).band
        band = rules if rank(rules) > rank(policy) else policy  # = citizen_check, raise-only
        rows.append({"policy": policy.value, "rules": rules.value, "band": band.value})
    return pd.DataFrame(rows)


def rates(sub: pd.DataFrame, col: str) -> dict[str, object]:
    out: dict[str, object] = {}
    for lab, name in ((1, "scam"), (0, "genuine")):
        s = sub[sub.label == lab]
        out[name] = {
            "n": len(s),
            "flagged": wilson(int(s[col].isin([b.value for b in FLAG]).sum()), len(s)),
            "hold": wilson(int((s[col] == Band.HOLD.value).sum()), len(s)),
        }
    return out


def main() -> None:
    from satyapan.api.state import AppState
    from satyapan.settings import Settings

    df = pd.read_parquet(DATA / "table.parquet")
    test = df[df.split == "test"].reset_index(drop=True)
    state = AppState.build(Settings())
    t0 = time.time()
    test = pd.concat([test, answers(state, test.text.tolist())], axis=1)
    ms = 1000 * (time.time() - t0) / len(test)
    report: dict[str, object] = {"n_test_texts": len(test), "ms_per_text": round(ms, 1),
                                 "max_chars": MAX_CHARS, "datasets": {}}  # fmt: skip
    for ds in [*sorted(test.dataset.unique()), "ALL"]:
        sub = test if ds == "ALL" else test[test.dataset == ds]
        report["datasets"][ds] = {  # type: ignore[index]
            col: rates(sub, col) for col in ("band", "policy", "rules")
        }
    test["lang_group"] = test.lang.map(LANG_GROUP).fillna("Other Indian languages")
    report["languages"] = {
        g: rates(test[test.lang_group == g], "band") for g in sorted(test.lang_group.unique())
    }
    out = ROOT / "results"
    (out / "consumer_text_eval.json").write_text(json.dumps(report, indent=1) + "\n")
    (out / "consumer_text_eval.md").write_text(render(report))
    print((out / "consumer_text_eval.md").read_text())


def _rate(w: dict) -> str:
    lo, hi = w["ci95"]
    return f"{100 * w['value']:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]"


def render(r: dict) -> str:
    lines = [
        "# The consumer path on open data (research/text/consumer_eval.py)",
        "",
        f"Held-out TEST texts of the 7 open sets (n = {r['n_test_texts']}), each sent through "
        "the Scam Check page's path: quick check (scam-text model + asks, band from the policy "
        "engine) and the impossible-claim rules, higher band wins. Nothing fitted here. "
        f"Flagged = VERIFY or HOLD. Wilson 95 %. {r['ms_per_text']} ms per text on this CPU.",
        "",
        "| Dataset | scams n | scams flagged | scams HOLD | genuine n | genuine flagged "
        "| genuine HOLD |",
        "|---|---|---|---|---|---|---|",
    ]
    for ds, block in r["datasets"].items():
        b = block["band"]
        lines.append(
            f"| {ds} | {b['scam']['n']} | {_rate(b['scam']['flagged'])} | "
            f"{_rate(b['scam']['hold'])} | {b['genuine']['n']} | "
            f"{_rate(b['genuine']['flagged'])} | {_rate(b['genuine']['hold'])} |"
        )
    lines += [
        "",
        "By language (whole path): Other Indian languages = Bengali, Gujarati, Marathi, "
        "Punjabi, Kashmiri, Kannada, Malayalam, Telugu, Assamese.",
        "",
        "| Language | scams n | scams flagged | genuine n | genuine flagged |",
        "|---|---|---|---|---|",
    ]
    for g, b in r["languages"].items():
        lines.append(
            f"| {g} | {b['scam']['n']} | {_rate(b['scam']['flagged']) if b['scam']['n'] else '–'}"
            f" | {b['genuine']['n']} | "
            f"{_rate(b['genuine']['flagged']) if b['genuine']['n'] else '–'} |"
        )
    a = r["datasets"]["ALL"]
    lines += [
        "",
        "What each part adds (ALL sets): flagged scams / flagged genuine",
        "",
        f"- policy path only (text model + asks): {_rate(a['policy']['scam']['flagged'])} / "
        f"{_rate(a['policy']['genuine']['flagged'])}",
        f"- impossible-claim rules only: {_rate(a['rules']['scam']['flagged'])} / "
        f"{_rate(a['rules']['genuine']['flagged'])}",
        f"- both (what the person sees): {_rate(a['band']['scam']['flagged'])} / "
        f"{_rate(a['band']['genuine']['flagged'])}",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
