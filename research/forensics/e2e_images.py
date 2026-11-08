"""End-to-end check of the image pipeline under the shipped verdict rules (held-out data).

    uv run python -m research.forensics.e2e_images [N] [--normalise]

Runs every image technique with every available model on N genuine MS COCO photographs and N
AI-generated images (SD 2.1 / SDXL / SD 3 / DALL·E 3 / Midjourney v6) drawn with a fixed seed
from the Defactify *test* shard (never used for selection or thresholds), then counts verdicts.
Rule, fixed before running: a false alarm is SYNTHETIC or MANIPULATED on a genuine photo; a
detection is SYNTHETIC on an AI image, "flagged" is SUSPICIOUS. The dataset's real and AI
images differ in size and format, which a model can exploit; --normalise first gives every
image the same form (centre square crop, 512 px, JPEG q90), as in the selection protocol.
Writes results/forensics_e2e_images[_normalised].{json,md}.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import numpy as np

from research.forensics.aigen_select import TEST

ROOT = Path(__file__).resolve().parents[2]
SEED = 20261108


def sample(path: Path, n: int, label: int, seed: int) -> list[bytes]:
    import pyarrow.parquet as pq

    tab = pq.read_table(path, columns=["Image", "Label_B"])
    lb = np.array(tab.column("Label_B").to_pylist())
    pool = np.where(lb == label)[0]
    rng = np.random.default_rng(seed)
    idx = rng.choice(pool, size=min(n, len(pool)), replace=False)
    col = tab.column("Image")
    return [col[int(i)].as_py()["bytes"] for i in sorted(idx)]


def normalise(data: bytes) -> bytes:
    import io

    from PIL import Image

    im = Image.open(io.BytesIO(data)).convert("RGB")
    s = min(im.size)
    left, top = (im.width - s) // 2, (im.height - s) // 2
    im = im.crop((left, top, left + s, top + s)).resize((512, 512), Image.BICUBIC)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def main() -> int:
    from satyapan.forensics.engine import analyze_bytes
    from satyapan.forensics.registry import registry

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    norm = "--normalise" in sys.argv
    n = int(args[0]) if args else 40
    suffix = "_normalised" if norm else ""
    OUT_JSON = ROOT / "results" / f"forensics_e2e_images{suffix}.json"
    OUT_MD = ROOT / "results" / f"forensics_e2e_images{suffix}.md"
    models = registry()
    out: dict[str, list[dict[str, object]]] = {"genuine": [], "ai": []}
    t0 = time.time()
    for name, label in (("genuine", 0), ("ai", 1)):
        for i, raw in enumerate(sample(TEST, n, label, SEED + label)):
            data = normalise(raw) if norm else raw
            with tempfile.TemporaryDirectory() as tmp:
                a, _ = analyze_bytes(data, f"{name}_{i:03d}.jpg", Path(tmp), models=models)
            v = a.verdict
            assert v is not None
            out[name].append({"i": i, "verdict": v.label.value, "confidence": v.confidence,
                              "top": v.rationale[:2]})  # fmt: skip
            print(f"{name:7s} {i:3d} {v.label.value:13s} {v.rationale[:1]}", flush=True)
    g = Counter(str(r["verdict"]) for r in out["genuine"])
    s = Counter(str(r["verdict"]) for r in out["ai"])
    fa = g["SYNTHETIC"] + g["MANIPULATED"]
    summary = {
        "n_genuine": len(out["genuine"]), "n_ai": len(out["ai"]),
        "genuine_verdicts": dict(g), "ai_verdicts": dict(s),
        "false_alarms": fa, "ai_synthetic": s["SYNTHETIC"], "ai_suspicious": s["SUSPICIOUS"],
        "seconds": round(time.time() - t0, 1),
    }  # fmt: skip
    OUT_JSON.write_text(json.dumps({"summary": summary, "rows": out}, indent=1))
    lines = [
        "# Image pipeline end to end (Defactify test shard, held out)"
        + (" — normalised" if norm else " — native files"),
        "",
        f"`python -m research.forensics.e2e_images {n}{' --normalise' if norm else ''}` — all "
        "image techniques and models, shipped verdict rules"
        + (
            " (every image centre-cropped to 512 px, JPEG q90 first)."
            if norm
            else " (files as distributed; real and AI images differ in size and format)."
        ),
        "",
        "| Set | n | SYNTHETIC | MANIPULATED | SUSPICIOUS | NO_INDICATORS | INCONCLUSIVE |",
        "|---|---|---|---|---|---|---|",
    ]
    for label, c, k in (("Genuine MS COCO photos", g, "genuine"), ("AI-generated images", s, "ai")):
        lines.append(f"| {label} | {len(out[k])} | {c['SYNTHETIC']} | {c['MANIPULATED']} | "
                     f"{c['SUSPICIOUS']} | {c['NO_INDICATORS']} | {c['INCONCLUSIVE']} |")  # fmt: skip
    lines += ["", f"False alarms (SYNTHETIC or MANIPULATED on a genuine photo): **{fa} of "
              f"{len(out['genuine'])}**.", ""]  # fmt: skip
    OUT_MD.write_text("\n".join(lines))
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
