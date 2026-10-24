"""One command for the whole test kit: every benchmark, from download to results/.

    python -m research.run_all text            # ~1.5 h on 4 CPU cores
    python -m research.run_all video           # ~10 h on 4 CPU cores (no GPU needed)
    python -m research.run_all voice           # ~8 h on 4 CPU cores
    python -m research.run_all kit             # the whole product on a mixed test kit (~15 min)
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
        ("text-embed-baseline", ["research.text.embed_baseline"]),  # multilingual-e5 + LR
        ("text-consumer", ["research.text.consumer_eval"]),  # the Scam Check page's whole path
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
        ("video-fit-fusion", [V + "fit_fusion"]),  # our SBI CNN -> config/*__blend.json
        # Off-the-shelf Hugging Face detectors on the same crops (rule fixed in advance).
        ("video-external-orig", [V + "hf_baselines", "--score", "--conditions", "orig"]),
        ("video-external-calls", [V + "hf_baselines", "--score", "--gated",
                                  "--conditions", "call720", "call360"]),
        ("video-external-report", [V + "hf_baselines", "--report"]),  # + the val-only selection
        # The selected detector (GenD, results/video_selection.json) in the product's CNN slot.
        ("video-export-gend", [V + "export_gend"]),
        ("video-tables-gend-orig", [V + "tables", "--cnn", "gend_clip_l14", "--condition", "orig"]),
        ("video-tables-gend-call720", [V + "tables", "--cnn", "gend_clip_l14",
                                       "--condition", "call720"]),
        ("video-tables-gend-call360", [V + "tables", "--cnn", "gend_clip_l14",
                                       "--condition", "call360"]),
        ("video-fit-gend", [V + "fit_fusion", "--cnn", "gend_clip_l14"]),
        # The frozen test runs (shipped GenD config and the SBI fallback), lip-sync, manifest.
        ("video-benchmark", [V + "run_benchmark", "--cnn", "gend_clip_l14"]),
        ("video-benchmark-blend", [V + "run_benchmark", "--cnn", "blend"]),
        ("video-lipsync", [V + "lipsync_eval"]),
        ("video-image-eval", [V + "image_eval"]),  # one crop = one photo (the photo check)
        ("video-photo-whatsapp", [V + "photo_whatsapp"]),  # the same photos after a re-encode
        ("video-manifest", [V + "manifest"]),
    ],
    "voice": [
        ("voice-data", ["research.voice.data"]),  # In-the-Wild + ASVspoof 2019, 5 s clips
        ("voice-bench", ["research.voice.bench"]),  # gate -> selection -> thresholds -> test
        ("voice-export", ["research.voice.export"]),  # two-file ONNX the product reads
    ],
    # The whole product on a mixed kit built from the test sets (run after text/video/voice).
    "kit": [
        ("kit-build", ["research.kit", "build"]),
        ("kit-run", ["research.kit", "run"]),
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
