"""Print the 12-scenario decision-relevance table (rules-only band vs full band).

Labelled ILLUSTRATIVE (n=12, team-authored fixtures). It shows WHERE detectors change the
outcome (regions R1-R4) and where the floor alone decides. It is NOT a research result.
Writes results/decision_relevance.md as well.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from satyapan.master import load_master  # noqa: E402
from satyapan.policy import decide_rules_only  # noqa: E402
from satyapan.repository import CaseRepository  # noqa: E402


def main() -> None:
    data = ROOT / "data" / "demo"
    master = load_master(data)
    repo = CaseRepository.from_fixtures(master, data / "cases")
    expected = json.loads((data / "expected_decisions.json").read_text(encoding="utf-8"))
    rows = [
        "| Case | Scenario | Action | Rules-only | Full | Changed? | Region |",
        "|---|---|---|---|---|---|---|",
    ]
    changed = 0
    for c in repo.all_cases():
        assert c.decision is not None
        r = decide_rules_only(c, master).band.value
        f = c.decision.band.value
        changed += r != f
        rows.append(
            f"| {c.id} | {c.title} | {c.decision.action_type.value} | {r} | {f} | "
            f"{'yes' if r != f else 'no'} | {expected[c.id]['region']} |"
        )
    text = "\n".join(rows) + f"\n\nIllustrative, n={len(repo.cases)} team-authored scenarios. "
    text += f"Detectors changed the outcome in {changed}/{len(repo.cases)}.\n"
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "decision_relevance.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
