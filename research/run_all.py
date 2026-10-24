"""One command for the whole test kit: every benchmark, from download to results/.

    python -m research.run_all text            # ~1.5 h on 4 CPU cores
    python -m research.run_all video           # ~10 h on 4 CPU cores (no GPU needed)
    python -m research.run_all video --from video-tables     # resume from a stage
    python -m research.run_all --list

Same commands on Windows, macOS and Linux (Python only; ffmpeg on PATH for the call-channel
simulation). Data never enters the repo: $SATYAPAN_TEXT_DATA / $SATYAPAN_VIDEO_DATA (default
../satyapan-data/...). Every stage is deterministic (SEED = 20261024) and skips work whose
output already exists, so a crashed run is resumed by running the same command again.
The protocol, the order of the stages and what may look at which split are documented in
docs/BENCHMARKS.md; the stages below are exactly the ones used for the committed results.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

V = "research.video."
STAGES: dict[str, list[tuple[str, list[str]]]] = {
    "text": [
        ("text-data", ["research.text.data"]),  # download (sha256-pinned), dedup, splits
        ("text-bench", ["research.text.bench"]),  # CV -> frozen thresholds -> test once
        ("text-neardup", ["research.text.neardup"]),  # near-copy audit of the test splits
    ],
    "video": [
        ("video-data", [V + "data", "ffpp", "dfdc"]),
        # The blend CNN: self-blended images from REAL training videos only.
        ("video-sbi-prep", [V + "sbi_prep"]),
        ("video-train-sbi", [V + "train_sbi"]),
        # Per-frame cues + face crops; the call conditions re-encode with VP8 first.
        ("video-extract-orig", [V + "extract", "--sets", "ffpp", "dfdc",
                                "--splits", "fusion_train", "val", "test", "xtest"]),
        ("video-extract-call360", [V + "extract", "--sets", "ffpp", "dfdc",
                                   "--splits", "val", "test", "xtest", "--condition", "call360"]),
        ("video-extract-call720", [V + "extract", "--sets", "ffpp", "--splits", "val", "test",
                                   "--val-reals-only", "--condition", "call720"]),
        ("video-tables-orig", [V + "tables", "--condition", "orig"]),
        ("video-tables-call720", [V + "tables", "--condition", "call720"]),
        ("video-tables-call360", [V + "tables", "--condition", "call360"]),
        # Train/val only: fusion CV, cue-set choice (1-SE rule), thresholds.
        ("video-fit-fusion", [V + "fit_fusion"]),
        # Off-the-shelf Hugging Face detectors on the same crops (rule fixed in advance).
        ("video-external-orig", [V + "hf_baselines", "--score", "--conditions", "orig"]),
        ("video-external-calls", [V + "hf_baselines", "--score", "--gated",
                                  "--conditions", "call720", "call360"]),
        ("video-external-report", [V + "hf_baselines", "--report"]),
        # The single frozen test run, then the zero-parameter lip-sync test and the manifest.
        ("video-benchmark", [V + "run_benchmark"]),
        ("video-lipsync", [V + "lipsync_eval"]),
        ("video-manifest", [V + "manifest"]),
    ],
}  # fmt: skip


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("suite", nargs="?", choices=sorted(STAGES))
    ap.add_argument("--from", dest="start", help="resume from this stage name")
    ap.add_argument("--only", help="run just this stage")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list or not a.suite:
        for suite, stages in STAGES.items():
            for name, cmd in stages:
                print(f"{suite:6} {name:24} python -m {' '.join(cmd)}")
        return 0
    stages = STAGES[a.suite]
    names = [n for n, _ in stages]
    if a.only:
        stages = [s for s in stages if s[0] == a.only]
    elif a.start:
        stages = stages[names.index(a.start) :]
    for name, cmd in stages:
        t0 = time.time()
        print(f"== {name}: python -m {' '.join(cmd)}", flush=True)
        if subprocess.call([sys.executable, "-m", *cmd]) != 0:
            print(f"!! {name} failed; fix it and rerun with --from {name}", flush=True)
            return 1
        print(f"== {name} done in {(time.time() - t0) / 60:.1f} min", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
