"""Voice Seal evaluation through real codec chains, using the IN-REPO module (satyapan.seal).

For every synthetic voice (research/seal/gen_voices.py) and every chain in channels.CHAINS:
  H1   sealed by Rajesh's session for meeting M, verified as Rajesh / M        -> should verify
  H0u  unsealed speech (stands for ANY clone or voice conversion of Rajesh)    -> must not
  H0r  relay: audio sealed for meeting M' replayed live into meeting M          -> must not
  H0s  replay: audio sealed at epoch e played back at epoch e+3                 -> must not
  H0i  wrong identity: audio sealed by Meera's key, claimed as Rajesh           -> must not
The receiver does not know the network delay (0-120 ms, drawn per voice x chain from a seeded
generator); it runs the live protocol (voiceseal.detect, LIVE_LOOKS, +/-200 ms acquisition).

Outputs (numbers come only from running this script):
  results/seal_codec_eval.csv    one row per chain
  results/seal_codec_epochs.csv  one row per (voice, chain, case, epoch): the raw z values
  results/seal_summary.json      pooled numbers, protocol, thresholds + DATA MANIFEST
                                 (sha256 of every audio file, generator, voices, seeds, commit)

Run: python research/seal/run_codec_eval.py [--workers 2] [--chains clean,opus16_voicenote]
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import wavfile

try:
    from research.seal import channels as ch
    from research.seal.common import (
        RESULTS,
        VOICES_DIR,
        git_commit,
        sha256_file,
        tool_versions,
    )
except ImportError:  # run as a plain script
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from research.seal import channels as ch
    from research.seal.common import (
        RESULTS,
        VOICES_DIR,
        git_commit,
        sha256_file,
        tool_versions,
    )

from satyapan.seal import tesla  # noqa: E402
from satyapan.seal import voiceseal as vs  # noqa: E402

SEED = 2026  # numpy Generator seed for delays / packet loss / noise (experimental conditions)
MEET, MEET_OTHER = "meet:abc-defg-hij", "meet:xyz-uvwq-rst"
RAJESH_SEED, MEERA_SEED = b"eval-rajesh-session", b"eval-meera-session"
ACQ_LAG = 25  # +/-25 frames = +/-200 ms acquisition search
REPLAY_SHIFT = 3
CASES = ["H1_sealed", "H0u_unsealed_or_clone", "H0r_relay", "H0s_replay_e+3", "H0i_wrong_identity"]
LANG = {"af": "en", "am": "en", "bf": "en", "bm": "en", "hf": "hi", "hm": "hi"}


def load_voice(path: Path) -> np.ndarray:
    sr, x = wavfile.read(path)
    assert sr == vs.SR, (path, sr)
    return x.astype(np.float64) / 32768.0


def run_voice(args: tuple[int, str, list[str]]) -> dict[str, Any]:
    vi, voice, chains = args
    x = load_voice(VOICES_DIR / f"{voice}.wav")
    _, k_raj = tesla.make_chain(RAJESH_SEED, 400)
    _, k_mee = tesla.make_chain(MEERA_SEED, 400)
    n_ep = int(len(x) / vs.SR / vs.DEFAULT_PARAMS.epoch_s) - 1  # last epoch may be cut by delay
    t0 = time.perf_counter()
    sealed = vs.embed(x, k_raj, MEET)
    embed_rtf = (time.perf_counter() - t0) / (len(x) / vs.SR)
    streams = {
        "sealed": sealed,
        "clean": x,
        "relay": vs.embed(x, k_raj, MEET_OTHER),
        "meera": vs.embed(x, k_mee, MEET),
    }
    pats = [vs.epoch_pattern(k_raj[e], MEET, e) for e in range(n_ep)]
    stale = [vs.epoch_pattern(k_raj[e + REPLAY_SHIFT], MEET, e + REPLAY_SHIFT) for e in range(n_ep)]
    rows: list[dict[str, Any]] = []
    sessions: list[dict[str, Any]] = []
    detect_ms: list[float] = []
    for ci, chain in enumerate(chains):
        rng = np.random.default_rng([SEED, vi, ci])
        delay = int(rng.uniform(0, 0.12) * vs.SR)
        pad = np.zeros(delay)
        fn = ch.CHAINS[chain][1]
        feats = {k: vs.features(fn(np.concatenate([pad, s]), rng)) for k, s in streams.items()}
        plan = {
            "H1_sealed": (feats["sealed"], pats),
            "H0u_unsealed_or_clone": (feats["clean"], pats),
            "H0r_relay": (feats["relay"], pats),
            "H0s_replay_e+3": (feats["sealed"], stale),
            "H0i_wrong_identity": (feats["meera"], pats),
        }
        for case, (feat, pp) in plan.items():
            t1 = time.perf_counter()
            d = vs.detect(feat, pp, range(-ACQ_LAG, ACQ_LAG + 1), looks=vs.LIVE_LOOKS)
            detect_ms.append((time.perf_counter() - t1) * 1000)
            sessions.append(
                {
                    "voice": voice,
                    "chain": chain,
                    "case": case,
                    "sealed": d.sealed,
                    "decided_by": d.decided_by,
                    "time_to_verdict_s": d.time_to_verdict_s(),
                    "acq_stat": round(d.acquisition_statistic, 3),
                    "lag_frames": d.offset_frames,
                    "true_delay_frames": round(delay / vs.HOP, 2),
                }
            )
            for er in d.epochs:
                rows.append(
                    {
                        "voice": voice,
                        "chain": chain,
                        "case": case,
                        "epoch": er.epoch,
                        "z": round(er.z, 3),
                        "cells": er.cells,
                        "post_acquisition": er.epoch >= max(vs.LIVE_LOOKS),
                    }
                )
    return {
        "voice": voice,
        "rows": rows,
        "sessions": sessions,
        "embed_rtf": embed_rtf,
        "snr_db": vs.snr_db(x, sealed),
        "detect_ms": detect_ms,
        "seconds": len(x) / vs.SR,
    }


def summarise(
    chains: list[str], rows: list[dict[str, Any]], sessions: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_chain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in sessions:
        by_chain[s["chain"]].append(s)
    zs: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in rows:
        if r["post_acquisition"] and r["cells"] > 0:
            zs[(r["chain"], "H1" if r["case"] == "H1_sealed" else "H0")].append(r["z"])
    table = []
    for c in chains:
        ss = by_chain[c]
        h1 = [s for s in ss if s["case"] == "H1_sealed"]
        h0 = [s for s in ss if s["case"] != "H1_sealed"]
        t = [s["time_to_verdict_s"] for s in h1 if s["sealed"]]
        z1, z0 = np.array(zs[(c, "H1")]), np.array(zs[(c, "H0")])
        table.append(
            {
                "chain": c,
                "description": ch.CHAINS[c][0],
                "n_sessions_genuine": len(h1),
                "genuine_verified": sum(s["sealed"] for s in h1),
                "n_sessions_attack": len(h0),
                "attacks_falsely_sealed": sum(s["sealed"] for s in h0),
                "median_time_to_verdict_s": float(np.median(t)) if t else None,
                "max_time_to_verdict_s": float(np.max(t)) if t else None,
                "genuine_epochs_post_acq": len(z1),
                "genuine_z_mean": round(float(z1.mean()), 3),
                "genuine_epoch_rate_z_ge_4": round(float((z1 >= vs.TAU_EPOCH).mean()), 4),
                "attack_epochs_post_acq": len(z0),
                "attack_z_mean": round(float(z0.mean()), 3),
                "attack_z_std": round(float(z0.std()), 3),
                "attack_z_max": round(float(z0.max()), 3),
            }
        )
    h0_all = np.array(
        [
            r["z"]
            for r in rows
            if r["post_acquisition"] and r["cells"] > 0 and r["case"] != "H1_sealed"
        ]
    )
    h0_by_case = {
        case: [
            r["z"] for r in rows if r["post_acquisition"] and r["cells"] > 0 and r["case"] == case
        ]
        for case in CASES[1:]
    }
    pooled = {
        "attack_epochs": len(h0_all),
        "attack_z_mean": round(float(h0_all.mean()), 4),
        "attack_z_std": round(float(h0_all.std()), 4),
        "attack_z_max": round(float(h0_all.max()), 3),
        "attack_epochs_z_ge_4": int((h0_all >= vs.TAU_EPOCH).sum()),
        "attack_z_by_case": {
            k: {
                "n": len(v),
                "mean": round(float(np.mean(v)), 3),
                "std": round(float(np.std(v)), 3),
                "max": round(float(np.max(v)), 3),
            }
            for k, v in h0_by_case.items()
        },
        "attack_sessions": sum(s["case"] != "H1_sealed" for s in sessions),
        "attack_sessions_falsely_sealed": sum(
            s["sealed"] for s in sessions if s["case"] != "H1_sealed"
        ),
        "genuine_sessions": sum(s["case"] == "H1_sealed" for s in sessions),
        "genuine_sessions_verified": sum(s["sealed"] for s in sessions if s["case"] == "H1_sealed"),
        "genuine_decided_by": dict(
            Counter(s["decided_by"] for s in sessions if s["case"] == "H1_sealed")
        ),
        "genuine_missed": [
            {"voice": s["voice"], "chain": s["chain"]}
            for s in sessions
            if s["case"] == "H1_sealed" and not s["sealed"]
        ],
        "lag_error_frames_genuine_median": float(
            np.median(
                [
                    abs(s["lag_frames"] - s["true_delay_frames"])
                    for s in sessions
                    if s["case"] == "H1_sealed"
                ]
            )
        ),
    }
    by_lang: dict[str, Any] = {}
    for lang in ("en", "hi"):
        z1 = [
            r["z"]
            for r in rows
            if r["post_acquisition"]
            and r["cells"] > 0
            and r["case"] == "H1_sealed"
            and LANG[r["voice"][:2]] == lang
        ]
        z0 = [
            r["z"]
            for r in rows
            if r["post_acquisition"]
            and r["cells"] > 0
            and r["case"] != "H1_sealed"
            and LANG[r["voice"][:2]] == lang
        ]
        by_lang[lang] = {
            "genuine_z_mean": round(float(np.mean(z1)), 3),
            "attack_z_mean": round(float(np.mean(z0)), 3),
            "attack_z_std": round(float(np.std(z0)), 3),
            "n_attack_epochs": len(z0),
        }
    pooled["by_language"] = by_lang
    return table, pooled


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--chains", default=",".join(ch.CHAINS))
    ap.add_argument("--voices", default="")
    a = ap.parse_args()
    chains = [c for c in a.chains.split(",") if c]
    voices = sorted(p.stem for p in VOICES_DIR.glob("*.wav"))
    if a.voices:
        voices = [v for v in voices if v in a.voices.split(",")]
    if not voices:
        raise SystemExit(f"no voices in {VOICES_DIR}: run research/seal/gen_voices.py first")
    manifest = {
        "generator": "Kokoro-82M int8 ONNX (kokoro-onnx), stock voices; "
        "research/seal/gen_voices.py",
        "data_dir": "$SATYAPAN_SEAL_DATA/voices (outside the repo; audio is never committed)",
        "files": {f"{v}.wav": sha256_file(VOICES_DIR / f"{v}.wav") for v in voices},
        "voices": voices,
        "seeds": {
            "conditions_numpy_seed": SEED,
            "rng_per_voice_chain": "np.random.default_rng([SEED, voice_index, chain_index])",
            "rajesh_chain_seed": RAJESH_SEED.decode(),
            "meera_chain_seed": MEERA_SEED.decode(),
        },
        "git_commit": git_commit(),
        "tools": tool_versions(),
    }
    t0 = time.time()
    jobs = [(i, v, chains) for i, v in enumerate(voices)]
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        outs = list(ex.map(run_voice, jobs))
    rows = [r for o in outs for r in o["rows"]]
    sessions = [s for o in outs for s in o["sessions"]]
    table, pooled = summarise(chains, rows, sessions)
    RESULTS.mkdir(exist_ok=True)
    with (RESULTS / "seal_codec_eval.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    with (RESULTS / "seal_codec_epochs.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    p = vs.DEFAULT_PARAMS
    summary = {
        "what": "Voice Seal through real codec chains (synthetic TTS voices; illustrative, n=10)",
        "script": "research/seal/run_codec_eval.py",
        "module": vs.VERSION,
        "params": {
            "params_id": p.params_id,
            "amp_db": p.amp_db,
            "n_bands": p.n_bands,
            "band_hz": [p.f_lo, p.f_hi],
            "chip_s": p.chip_s,
            "epoch_s": p.epoch_s,
        },
        "protocol": {
            "name": "v2: acquire lag once (Bonferroni over candidates), then fixed-lag scoring",
            "acquisition_lags_frames": [-ACQ_LAG, ACQ_LAG],
            "looks": list(vs.LIVE_LOOKS),
            "tau_acquisition": round(vs.tau_acquisition(2 * ACQ_LAG + 1), 3),
            "alpha_per_acquisition_look": vs.ALPHA_ACQ,
            "stouffer_alpha_spending_total": vs.ALPHA_STOUFFER,
            "tau_epoch": vs.TAU_EPOCH,
            "false_seal_budget_per_session_gaussian": len(vs.LIVE_LOOKS) * vs.ALPHA_ACQ
            + vs.ALPHA_STOUFFER,
            "hoeffding_tail_at_tau_acq": vs.hoeffding_tail(vs.tau_acquisition(2 * ACQ_LAG + 1)),
            "time_to_verdict": "seconds of sealed speech from the first sealed epoch; key "
            "disclosure latency (<= 1 s) not included",
        },
        "pooled": pooled,
        "quality": {
            "seal_waveform_snr_db_mean": round(float(np.mean([o["snr_db"] for o in outs])), 2),
            "note": "SNR is meaningless for a level pattern; see results/seal_quality.json",
        },
        "compute": {
            "embed_rtf_python_mean": round(float(np.mean([o["embed_rtf"] for o in outs])), 5),
            "detect_ms_per_session_median": round(
                float(np.median([m for o in outs for m in o["detect_ms"]])), 1
            ),
            "wall_clock_s": round(time.time() - t0, 1),
            "audio_seconds_total": round(sum(o["seconds"] for o in outs), 1),
        },
        "chains": table,
        "manifest": manifest,
    }
    (RESULTS / "seal_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps(pooled, indent=1))
    for r in table:
        print(
            f"{r['chain']:18s} genuine {r['genuine_verified']}/{r['n_sessions_genuine']} "
            f"t50={r['median_time_to_verdict_s']} z1={r['genuine_z_mean']:.2f} | attacks "
            f"{r['attacks_falsely_sealed']}/{r['n_sessions_attack']} "
            f"z0 {r['attack_z_mean']:+.2f}/{r['attack_z_std']:.2f} max {r['attack_z_max']:.2f}"
        )


if __name__ == "__main__":
    main()
