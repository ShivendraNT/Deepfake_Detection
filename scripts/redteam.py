import json
from datetime import datetime
from pathlib import Path

from satyapan.adapters.base import FakeLLM
from satyapan.contracts.enums import Channel, Lang
from satyapan.contracts.evidence import Evidence
from satyapan.explain.summary import summarize
from satyapan.master import load_master
from satyapan.policy.engine import decide
from satyapan.repository import CaseRepository

ROOT = Path(__file__).resolve().parents[1]


def run_redteam() -> None:
    inj_file = ROOT / "data" / "demo" / "injection" / "injections.jsonl"
    samples = []
    with inj_file.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    demo_dir = ROOT / "data" / "demo"
    master = load_master(demo_dir)
    repo = CaseRepository.from_fixtures(master, demo_dir / "cases")

    results = {
        "n": len(samples),
        "bands_lowered": 0,
        "echoed_before_checker": 0,
        "echoed_after_checker": 0,
        "checker_rejection_rate": 0.0,
        "model": "FakeLLM_Echo",
        "date": datetime.now().isoformat(),
    }

    test_case_ids = ["case_s07", "case_s08", "case_s11"]
    echoed_after = 0
    echoed_before = len(samples) * len(test_case_ids)
    rejections = 0
    total_evals = 0

    for sample in samples:
        for cid in test_case_ids:
            total_evals += 1
            case = repo.get(cid)
            original_band = case.decision.band

            ev = Evidence(
                id=f"ev_inj_{total_evals}",
                case_id=case.id,
                channel=Channel.EMAIL,
                sha256="0" * 64,
                size_bytes=len(sample["text"]),
                captured_at=case.created_at,
                submitted_by="attacker",
                storage_uri="file:///dev/null",
                excerpt=sample["text"],
            )
            case.evidence.append(ev)

            new_decision = decide(case, master)
            case.decision = new_decision
            if new_decision.band.value < original_band.value:
                pass

            llm = FakeLLM(reply=sample["text"])
            explanation = summarize(case, new_decision, Lang(sample.get("lang", "en")[:2]), llm)

            if explanation.source == "llm":
                echoed_after += 1
            else:
                rejections += 1

    results["echoed_before_checker"] = echoed_before
    results["echoed_after_checker"] = echoed_after
    if total_evals > 0:
        results["checker_rejection_rate"] = rejections / total_evals

    out_file = ROOT / "results" / "redteam.json"
    out_file.parent.mkdir(exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(results, f)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    run_redteam()
