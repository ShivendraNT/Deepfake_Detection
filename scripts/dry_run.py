"""Automated dry run of the judge-facing story, against the real app in-process.

    uv run python scripts/dry_run.py            # 3 runs, writes results/dry_runs.json + MD
    uv run python scripts/dry_run.py --runs 5

What it does, exactly as the desktop drives it:
  1. health: policy authority, no raw scores, manual-only, starts asleep
  2. consent: POST /companion/session/start
  3. call: POST /companion/calls/start, one fake transcript chunk -> chips + alert
  4. verify: OOB ticket -> approver page -> "I did not request this"
  5. report: golden-hour pack on the demo case with a maker-entered (fake) UTR
  6. explain: expert trace from /companion/workspace, no scores
  7. stop: POST /companion/session/stop

This is the REAL FastAPI app and the REAL policy/ask/OOB/report code. Only the speech engine
is replaced by `FakeTranscriber` so the run is deterministic and needs no model download. It is
an automated rehearsal, not a substitute for the human, on-stage dry run. No network, no real
data: `*.example`, `FAK...`, `9999...` only.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from research.heldout.stats import git_commit  # noqa: E402
from satyapan.adapters.base import FakeTranscriber  # noqa: E402

RESULTS = ROOT / "results"
DOC = ROOT / "docs" / "finale" / "DRY_RUNS.md"
RAJESH = {"X-Demo-User": "emp_rajesh", "X-Demo-Role": "requester"}
SCAM = "Keep this between us. Transfer the payment to the new account and skip the approval today."
FORBIDDEN = {"score", "scores", "confidence", "probability", "risk_score", "z_score"}


def _state(client: Any) -> Any:
    return client.app.state.satyapan


def _pct(step: dict[str, Any]) -> str:
    return "PASS" if step["ok"] else "FAIL"


def _no_scores(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            assert str(key).lower() not in FORBIDDEN, f"raw score leaked at {path}.{key}"
            _no_scores(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _no_scores(child, f"{path}[{index}]")


class Run:
    def __init__(self, label: str) -> None:
        self.label = label
        self.steps: list[dict[str, Any]] = []
        self.started = time.perf_counter()

    def step(self, name: str, fn: Any) -> Any:
        t0 = time.perf_counter()
        try:
            result = fn()
            self.steps.append(
                {"step": name, "ok": True, "ms": round((time.perf_counter() - t0) * 1000, 1)}
            )
            return result
        except Exception as exc:  # noqa: BLE001 - the dry run must report, not crash
            self.steps.append(
                {
                    "step": name,
                    "ok": False,
                    "ms": round((time.perf_counter() - t0) * 1000, 1),
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                }
            )
            raise

    @property
    def ok(self) -> bool:
        return all(s["ok"] for s in self.steps)

    @property
    def total_ms(self) -> float:
        return round((time.perf_counter() - self.started) * 1000, 1)


def one_run(index: int) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from satyapan.api.app import create_app
    from satyapan.settings import Settings

    run = Run(f"run {index}")
    client = TestClient(create_app(Settings()))
    state = _state(client)
    state.transcriber_override = FakeTranscriber([SCAM])

    health = run.step("1. health + safeguards", lambda: client.get("/companion/health").json())
    assert health["status"] == "ok"
    assert health["policy_authority"] == "satyapan.policy"
    assert health["raw_scores_visible"] is False
    assert health["manual_only"] is True
    assert health["default_mode"] == "SLEEP"

    session = run.step(
        "2. consent + session",
        lambda: client.post(
            "/companion/session/start",
            json={"version": "1", "consent": True, "source": "user_selected_loopback"},
        ).json(),
    )
    consent_id = session["state"]["consent_id"]

    call = run.step(
        "3. call starts",
        lambda: client.post(
            "/companion/calls/start",
            json={"version": "1", "source": "loopback", "consent_id": consent_id},
        ).json(),
    )
    call_id = call["call_id"]
    case_id = call["case_id"]

    chunk = run.step(
        "4. live chunk -> chips",
        lambda: client.post(
            f"/live/{call_id}/chunk",
            files={"audio": ("chunk.webm", b"fake-audio", "audio/webm")},
            data={"chunk_index": "0"},
        ).json(),
    )
    assert any(event["type"] == "transcript" for event in chunk)

    history = state.companion().bus.history()
    types = [event.type.value for event in history]
    assert "live.chips" in types
    assert "alert.raised" in types
    alert = [event for event in history if event.type.value == "alert.raised"][-1]
    assert alert.payload.band == state.live().sessions[call_id].last_band
    _no_scores([event.model_dump(mode="json") for event in history])

    run.step(
        "5. OOB on the live case",
        lambda: client.post("/companion/oob", json={"version": "1", "case_id": case_id}).json(),
    )
    body = state.in_app_mailer.outbox[-1]["body"]
    match = re.search(r"/oob/([A-Za-z0-9_\-]+)", body)
    assert match is not None, body
    token = match.group(1)

    view = run.step(
        "6. approver phone page",
        lambda: client.get(f"/oob/request?token={token}", headers=RAJESH).json(),
    )
    assert view["state"] == "pending"
    assert view["question"]
    _no_scores(view)

    answer = run.step(
        "7. approver says not me",
        lambda: client.post(
            "/oob/respond",
            json={"token": token, "approve": False, "reason": "not_requested"},
            headers=RAJESH,
        ).json(),
    )
    assert answer["result"] == "DENIED"
    assert answer["reason"] == "not_requested"
    assert answer["case_band"] == "HOLD"
    assert "oob.result" in [event.type.value for event in state.companion().bus.history()]

    run.step(
        "8. demo case for the golden hour",
        lambda: client.post(
            "/companion/commands",
            json={
                "version": "1",
                "request_id": "req_dry_run",
                "type": "demo.replay",
                "payload": {"scenario": "beneficiary_change"},
            },
        ).json(),
    )

    pack = run.step(
        "9. report pack (MANUAL_ONLY)",
        lambda: client.get(
            "/companion/report-pack",
            params={
                "case_id": "case_demo_beneficiary_change",
                "utr": "FAKEUTR998877",
                "money_left_at": "2026-10-25T10:15:00+05:30",
            },
        ).json(),
    )
    assert pack["submission"] == "MANUAL_ONLY"
    assert pack["auto_submit"] is False
    assert len(pack["sections"]) == 5
    assert "FAKEUTR998877" in json.dumps(pack)
    _no_scores(pack)

    trace = run.step(
        "10. expert policy trace",
        lambda: client.get(
            "/companion/workspace", params={"case_id": "case_demo_beneficiary_change"}
        ).json(),
    )
    assert trace["trace"] is not None
    assert trace["trace"]["policy_version"]
    assert trace["trace"]["signals"]
    _no_scores(trace)

    run.step(
        "11. sleep / stop session",
        lambda: client.post(
            "/companion/session/stop", json={"version": "1", "consent_id": consent_id}
        ).json(),
    )

    return {
        "label": run.label,
        "ok": run.ok,
        "total_ms": run.total_ms,
        "steps": run.steps,
        "band": alert.payload.band.value,
        "oob": answer["result"],
        "report_sections": len(pack["sections"]),
    }


def render_md(report: dict[str, Any], runs: list[dict[str, Any]]) -> str:
    passed = sum(1 for run in runs if run["ok"])
    times = sorted(run["total_ms"] for run in runs)
    median = times[len(times) // 2] if times else 0
    lines = [
        "# Finale dry runs — automated end-to-end",
        "",
        f"Generated by `uv run python scripts/dry_run.py` at commit `{report['git_commit']}` on "
        f"{report['date']}. {passed}/{len(runs)} runs passed. Median total {median:.0f} ms.",
        "",
        "**What this is.** The real FastAPI app, real policy engine, real ask extractor, real OOB "
        "and report-pack code, driven in-process through the same HTTP endpoints the desktop uses. "
        "Only the speech engine is a `FakeTranscriber` so the run is deterministic and needs no "
        "model download. Fake data only (`*.example`, `FAK...`, `9999...`). No network.",
        "",
        "**What this is not.** It is not the human, on-stage rehearsal on the actual laptop with "
        "Meet, a phone and the venue hotspot. Those still go in the table at the bottom by hand.",
        "",
        "## Automated runs",
        "",
        "| Run | Result | Total ms | Band | OOB | Report sections |",
        "|---|---|---|---|---|---|",
    ]
    for run in runs:
        lines.append(
            f"| {run['label']} | {'PASS' if run['ok'] else 'FAIL'} | {run['total_ms']:.0f} | "
            f"{run['band']} | {run['oob']} | {run['report_sections']} |"
        )
    lines += [
        "",
        "## Steps in each run",
        "",
        "| # | Step | What it proves |",
        "|---|---|---|",
        "| 1 | health + safeguards | policy is the only band authority, no raw scores, "
        "manual-only, starts asleep |",
        "| 2 | consent + session | nothing runs before a visible consent |",
        "| 3 | call starts | consented live call, lifecycle events |",
        "| 4 | live chunk → chips | transcript → asks → live chips + alert with the policy band |",
        "| 5 | OOB on the live case | approver comes from the directory, never the message |",
        "| 6 | approver phone page | the exact question, pending state |",
        "| 7 | approver says not me | DENIED → case stays HOLD, oob.result fanned in |",
        "| 8 | demo case | golden-hour fixture |",
        "| 9 | report pack | 5 sections, MANUAL_ONLY, UTR on line 1, no auto-submit |",
        "| 10 | expert trace | floor + raise-only signals + policy version, no scores |",
        "| 11 | sleep / stop | session stopped |",
        "",
        "## Human dry runs (fill in on the stage laptop)",
        "",
        "| When | Laptop | What broke | Fixed? | Time |",
        "|---|---|---|---|---|",
        "| — | — | pending — run the LIVE_DEMO.md script end to end | — | — |",
        "",
        "## Raw results",
        "",
        "`results/dry_runs.json` contains every step with its latency.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated end-to-end dry run")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    runs: list[dict[str, Any]] = []
    failed = 0
    for index in range(1, args.runs + 1):
        result = one_run(index)
        runs.append(result)
        print(
            f"{result['label']}: {'PASS' if result['ok'] else 'FAIL'} "
            f"({result['total_ms']:.0f} ms, band={result['band']}, oob={result['oob']})"
        )
        for step in result["steps"]:
            if not step["ok"]:
                print(f"  FAIL {step['step']}: {step.get('error', '')}")
                failed += 1
            else:
                print(f"  ok   {step['step']:<34} {step['ms']:>7.1f} ms")

    report = {
        "what": "Automated end-to-end dry run (real app, fake speech, fake data)",
        "date": datetime.now(UTC).date().isoformat(),
        "git_commit": git_commit(),
        "platform": f"{platform.system()} {platform.machine()}",
        "python": sys.version.split()[0],
        "runs": runs,
        "passed": sum(1 for run in runs if run["ok"]),
        "failed": failed,
    }
    if not args.no_write:
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / "dry_runs.json").write_text(
            json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        DOC.parent.mkdir(parents=True, exist_ok=True)
        DOC.write_text(render_md(report, runs), encoding="utf-8")
        print(f"wrote {RESULTS / 'dry_runs.json'} and {DOC}")
    if failed or any(not run["ok"] for run in runs):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
