"""Does forwarding a photo on WhatsApp hide a swapped face? A paired robustness test.

    python -m research.video.photo_whatsapp   # -> results/photo_whatsapp.{json,md}

The same held-out frames (FF++ c23 test, one frame per video, seeded 100 real + 100 fake) go
through the product's photo check (satyapan.imagecheck.face.ImageFaceChecker: tracker, crop,
GenD, frozen thresholds) twice: as stored, and after a WhatsApp-style re-encode (longest side at
most 1,600 px, JPEG quality 60). Nothing is fitted; the difference is paired per frame with
identity clusters resampled together.
"""

from __future__ import annotations

import io
import json
import random  # provenance: seeded-resampling-ok

import numpy as np
from PIL import Image

from research.metrics import auroc
from research.video.data import DATA, ROOT
from research.video.hf_baselines import items
from research.video.stats import cluster_ci, cluster_paired_diff, wilson

SEED = 20261024
N_PER_CLASS = 100


def whatsapp(rgb: np.ndarray, quality: int = 60, max_side: int = 1600) -> np.ndarray:
    img = Image.fromarray(rgb)
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGB"))


def main() -> None:
    from satyapan.imagecheck.face import ImageFaceChecker, decode_image

    frames = DATA / "frames" / "orig"
    pool = [it for it in items() if it.split == "test"
            and (frames / (it.key.replace("/", "__") + ".jpg")).exists()]  # fmt: skip
    rng = random.Random(SEED)
    picked = []
    for label in (0, 1):
        cand = sorted((it for it in pool if it.label == label), key=lambda it: it.key)
        picked += rng.sample(cand, min(N_PER_CLASS, len(cand)))
    checker = ImageFaceChecker.load()
    thr = checker.thresholds
    rows = []
    for it in picked:
        rgb = decode_image((frames / (it.key.replace("/", "__") + ".jpg")).read_bytes())
        a, b = checker.check(rgb), checker.check(whatsapp(rgb))
        rows.append({"key": it.key, "label": it.label, "identity": it.identity,
                     "method": it.method, "orig": a.logit, "wa": b.logit})  # fmt: skip
    ok = [r for r in rows if r["orig"] is not None and r["wa"] is not None]
    y = np.array([r["label"] for r in ok])
    g = np.array([r["identity"] for r in ok])
    s = {k: np.array([r[k] for r in ok], float) for k in ("orig", "wa")}

    def auc(yy, ss):
        return auroc(yy.tolist(), ss.tolist())

    out: dict = {
        "n_frames": len(rows),
        "n_with_face_both": len(ok),
        "quality": 60,
        "max_side": 1600,
        "thresholds": {"tau_hi": thr.tau_hi, "tau_lo": thr.tau_lo},
    }
    for k, name in (("orig", "as stored"), ("wa", "WhatsApp-style JPEG q60")):
        out[k] = {
            "name": name,
            "auc": cluster_ci(auc, y, s[k], g),
            "fakes_flagged_tau_lo": wilson(int((s[k][y == 1] >= thr.tau_lo).sum()), int(y.sum())),
            "reals_flagged_tau_lo": wilson(
                int((s[k][y == 0] >= thr.tau_lo).sum()), int((y == 0).sum())
            ),  # fmt: skip
            "fakes_tau_hi": wilson(int((s[k][y == 1] >= thr.tau_hi).sum()), int(y.sum())),
            "reals_tau_hi": wilson(int((s[k][y == 0] >= thr.tau_hi).sum()), int((y == 0).sum())),
        }
    out["delta_auc_wa_minus_orig"] = cluster_paired_diff(auc, y, s["wa"], s["orig"], g)
    out["mean_logit_shift"] = {
        "fake": round(float((s["wa"] - s["orig"])[y == 1].mean()), 4),
        "real": round(float((s["wa"] - s["orig"])[y == 0].mean()), 4),
    }
    res = ROOT / "results"
    (res / "photo_whatsapp.json").write_text(json.dumps(out, indent=1) + "\n")
    (res / "photo_whatsapp.md").write_text(render(out))
    print(render(out))


def _r(w: dict) -> str:
    lo, hi = w["ci95"]
    return f"{100 * w['value']:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}] ({w['k']}/{w['n']})"


def render(o: dict) -> str:
    d = o["delta_auc_wa_minus_orig"]
    lines = [
        "# Photo check after a WhatsApp-style re-encode (research/video/photo_whatsapp.py)",
        "",
        f"FF++ c23 test frames, seeded {o['n_frames']} (half real); {o['n_with_face_both']} had a "
        "usable face both times. Product photo check, frozen thresholds. Re-encode: longest "
        f"side <= {o['max_side']} px, JPEG quality {o['quality']}.",
        "",
        "| Version | AUC [95% CI] | fakes flagged (>= tau_lo) | reals flagged (>= tau_lo) "
        "| fakes >= tau_hi | reals >= tau_hi |",
        "|---|---|---|---|---|---|",
    ]
    for k in ("orig", "wa"):
        e = o[k]
        a = e["auc"]
        lines.append(f"| {e['name']} | {a['value']:.3f} [{a['low']:.3f}, {a['high']:.3f}] | "
                     f"{_r(e['fakes_flagged_tau_lo'])} | {_r(e['reals_flagged_tau_lo'])} | "
                     f"{_r(e['fakes_tau_hi'])} | {_r(e['reals_tau_hi'])} |")  # fmt: skip
    shift = o["mean_logit_shift"]
    lines += [
        "",
        f"Paired AUC change (re-encoded - stored): {d['value']:+.3f} "
        f"[{d['low']:+.3f}, {d['high']:+.3f}]. Mean logit shift: fakes {shift['fake']:+.3f}, "
        f"reals {shift['real']:+.3f}.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
