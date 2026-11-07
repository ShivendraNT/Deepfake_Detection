"""Choose the AI-generated image classifier for the Forensic Lab (pre-registered rule).

    uv run python -m research.forensics.aigen_select            # val comparison + test once
    uv run python -m research.forensics.aigen_select --export   # + ONNX + config/aigen_model.json

Data: Defactify (MS COCO photographs vs Stable Diffusion 2.1, SDXL, SD3, DALL-E 3 and
Midjourney v6; Label_A 0 = real). One validation shard for selection and thresholds, one test
shard scored once with the frozen choice. Images are never committed.

Conditions: `native` (as distributed) and `normalised` (centre square crop, 512 px, JPEG q90),
because the classes differ in size and aspect ratio and a model could learn those instead.

Rule (fixed before running): pick the highest validation AUC under `normalised`; thresholds
tau_lo / tau_hi are the 95th / 99th percentiles of the chosen model's real-image logits on
validation, taking the larger of the two conditions (conservative for unseen sizes).
"""

from __future__ import annotations

import argparse
import io
import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DATA = Path("/home/user/satyapan-data/aigen/data")
VAL = DATA / "validation-00000-of-00002.parquet"
TEST = DATA / "test-00000-of-00008.parquet"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "aigen_selection.json"
GEN = {0: "real (MS COCO)", 1: "SD 2.1", 2: "SDXL", 3: "SD 3", 4: "DALL-E 3", 5: "Midjourney v6"}


@dataclass(frozen=True)
class Candidate:
    name: str
    repo: str
    license: str
    kind: str = "hf"  # hf = AutoModelForImageClassification with its own processor


CANDIDATES = (
    Candidate("community_forensics", "buildborderless/CommunityForensics-DeepfakeDet-ViT", "MIT",
              "commfor"),
    Candidate("ateeqq_siglip", "Ateeqq/ai-vs-human-image-detector", "Apache-2.0"),
    Candidate("haywoodsloan_swinv2", "haywoodsloan/ai-image-detector-deploy", "Apache-2.0"),
    Candidate("nyuad_vit", "NYUAD-ComNets/NYUAD_AI-generated_images_detector", "Apache-2.0"),
    Candidate("organika_sdxl", "Organika/sdxl-detector", "CC-BY-NC-3.0"),
)  # fmt: skip

FAKE_WORDS = ("fake", "artificial", "ai", "generated", "synthetic", "machine")
REAL_WORDS = ("real", "human", "hum", "natural", "authentic", "realism")


def load_split(path: Path, n_real: int, n_per_gen: int, seed: int) -> list[tuple[bytes, int, int]]:
    import pyarrow.parquet as pq

    tab = pq.read_table(path, columns=["Image", "Label_A", "Label_B"])
    la = np.array(tab.column("Label_A").to_pylist())
    lb = np.array(tab.column("Label_B").to_pylist())
    rng = np.random.default_rng(seed)
    idx: list[int] = []
    for g in range(6):
        pool = np.where(lb == g)[0]
        k = n_real if g == 0 else n_per_gen
        idx += list(rng.choice(pool, size=min(k, len(pool)), replace=False))
    imgs = tab.column("Image")
    return [(imgs[int(i)].as_py()["bytes"], int(la[i]), int(lb[i])) for i in sorted(idx)]


def normalise(data: bytes) -> bytes:
    from PIL import Image

    img = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = img.size
    s = min(w, h)
    img = img.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
    img = img.resize((512, 512), Image.BICUBIC)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def scorer(c: Candidate):
    import torch
    from PIL import Image
    from transformers import AutoImageProcessor, AutoModelForImageClassification

    torch.set_num_threads(4)
    if c.kind == "commfor":
        from transformers import ViTForImageClassification

        net = ViTForImageClassification.from_pretrained(c.repo).eval()
        mean = np.array([0.48145466, 0.4578275, 0.40821073], np.float32)
        std = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)

        def prep(img: Image.Image) -> np.ndarray:
            w, h = img.size
            k = 440 / min(w, h)
            img = img.resize((max(440, round(w * k)), max(440, round(h * k))), Image.BICUBIC)
            w, h = img.size
            img = img.crop(((w - 384) // 2, (h - 384) // 2, (w - 384) // 2 + 384,
                            (h - 384) // 2 + 384))  # fmt: skip
            x = (np.asarray(img, np.float32) / 255.0 - mean) / std
            return x.transpose(2, 0, 1)

        def score(batch: list[Image.Image]) -> np.ndarray:
            x = torch.from_numpy(np.stack([prep(b) for b in batch]))
            with torch.inference_mode():
                return net(pixel_values=x).logits[:, 0].numpy()

        meta = {"size": 384, "resize": "shortest_crop", "pre_resize": 440,
                "mean": mean.tolist(), "std": std.tolist(), "single_logit": True}  # fmt: skip
        return score, net, meta
    proc = AutoImageProcessor.from_pretrained(c.repo)
    net = AutoModelForImageClassification.from_pretrained(c.repo).eval()
    labels = {int(k): str(v).lower() for k, v in net.config.id2label.items()}
    fake = next((k for k, v in labels.items() if any(w in v.split() or v.startswith(w)
                                                    for w in FAKE_WORDS)), None)  # fmt: skip
    real = next((k for k, v in labels.items() if any(w in v.split() or v.startswith(w)
                                                    for w in REAL_WORDS)), None)  # fmt: skip
    if fake is None or real is None or fake == real:
        raise RuntimeError(f"{c.name}: cannot map labels {labels}")

    def score(batch: list[Image.Image]) -> np.ndarray:
        inputs = proc(images=batch, return_tensors="pt")
        with torch.inference_mode():
            lg = net(**inputs).logits.float()
        lsm = torch.log_softmax(lg, dim=1)
        p = lsm[:, fake].exp().clamp(1e-9, 1 - 1e-9)
        return (torch.log(p) - torch.log1p(-p)).numpy()

    meta = {"labels": labels, "fake_index": fake, "real_index": real,
            "processor": proc.to_dict() if hasattr(proc, "to_dict") else {}}  # fmt: skip
    return score, net, meta


def run(c: Candidate, items: list[tuple[bytes, int, int]], cond: str, bs: int = 8) -> np.ndarray:
    from PIL import Image

    score, _, _ = scorer(c)
    out = []
    for i in range(0, len(items), bs):
        batch = []
        for data, _, _ in items[i : i + bs]:
            b = normalise(data) if cond == "normalised" else data
            batch.append(Image.open(io.BytesIO(b)).convert("RGB"))
        out.append(score(batch))
    return np.concatenate(out)


def auc(pos: np.ndarray, neg: np.ndarray) -> float:
    from scipy.stats import mannwhitneyu

    u = mannwhitneyu(pos, neg, alternative="two-sided").statistic
    return float(u / (len(pos) * len(neg)))


def tpr_at(pos: np.ndarray, neg: np.ndarray, fpr: float) -> tuple[float, float]:
    thr = float(np.quantile(neg, 1 - fpr))
    return float((pos > thr).mean()), thr


def metrics(scores: np.ndarray, items: list[tuple[bytes, int, int]], thr=None) -> dict:
    la = np.array([x[1] for x in items])
    lb = np.array([x[2] for x in items])
    pos, neg = scores[la == 1], scores[la == 0]
    m = {"n_real": int((la == 0).sum()), "n_fake": int((la == 1).sum()), "auc": auc(pos, neg)}
    m["tpr@1%"], m["thr@1%"] = tpr_at(pos, neg, 0.01)
    m["tpr@5%"], m["thr@5%"] = tpr_at(pos, neg, 0.05)
    if thr is not None:
        m["at_frozen"] = {
            "tau_hi": {"tpr": float((pos >= thr[1]).mean()), "fpr": float((neg >= thr[1]).mean())},
            "tau_lo": {"tpr": float((pos >= thr[0]).mean()), "fpr": float((neg >= thr[0]).mean())},
        }
        m["per_generator_tpr_tau_lo"] = {
            GEN[g]: float((scores[lb == g] >= thr[0]).mean()) for g in range(1, 6)
        }
        m["per_generator_tpr_tau_hi"] = {
            GEN[g]: float((scores[lb == g] >= thr[1]).mean()) for g in range(1, 6)
        }
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    val = load_split(VAL, 150, 30, seed=20261107)
    report: dict = {"rule": __doc__.split("Rule")[1].strip(), "val": {}, "candidates": {}}
    best, best_auc = None, -1.0
    val_scores = {}
    for c in CANDIDATES:
        if args.only and c.name not in args.only.split(","):
            continue
        t0 = time.time()
        try:
            res = {}
            for cond in ("normalised", "native"):
                s = run(c, val, cond)
                val_scores[(c.name, cond)] = s
                res[cond] = metrics(s, val)
        except Exception as exc:  # noqa: BLE001
            print(f"{c.name}: FAILED {exc}", flush=True)
            report["candidates"][c.name] = {"error": str(exc)}
            continue
        sec = (time.time() - t0) / (2 * len(val))
        res["seconds_per_image"] = round(sec, 3)
        report["candidates"][c.name] = {"repo": c.repo, "license": c.license, **res}
        print(f"{c.name}: val AUC normalised {res['normalised']['auc']:.3f} native "
              f"{res['native']['auc']:.3f}  TPR@1% {res['normalised']['tpr@1%']:.2f} "
              f"({sec:.2f}s/img)", flush=True)  # fmt: skip
        if res["normalised"]["auc"] > best_auc:
            best, best_auc = c, res["normalised"]["auc"]
    assert best is not None
    la = np.array([x[1] for x in val])
    reals = [val_scores[(best.name, cond)][la == 0] for cond in ("normalised", "native")]
    tau_lo = float(max(np.quantile(r, 0.95) for r in reals))
    tau_hi = float(max(np.quantile(r, 0.99) for r in reals))
    report["decision"] = best.name
    report["thresholds"] = {"tau_lo": tau_lo, "tau_hi": tau_hi}
    test = load_split(TEST, 400, 80, seed=20261108)
    report["test"] = {}
    for cond in ("normalised", "native"):
        s = run(best, test, cond)
        report["test"][cond] = metrics(s, test, (tau_lo, tau_hi))
        print(f"TEST {best.name} {cond}: AUC {report['test'][cond]['auc']:.3f} "
              f"at tau_hi TPR {report['test'][cond]['at_frozen']['tau_hi']['tpr']:.2f} "
              f"FPR {report['test'][cond]['at_frozen']['tau_hi']['fpr']:.3f}", flush=True)  # fmt: skip
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, default=float))
    print("wrote", OUT)
    if args.export:
        export(best, report)


def export(c: Candidate, report: dict) -> None:
    import torch

    _, net, meta = scorer(c)
    out_dir = ROOT / "models" / "forensics"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"aigen_{c.name}.onnx"
    size = int(meta.get("size") or 224)
    if c.kind != "commfor":
        proc = meta.get("processor", {})
        sz = proc.get("size", {})
        size = int(sz.get("height") or sz.get("shortest_edge") or size)

    class Wrap(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.net = net

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.net(pixel_values=x).logits

    x = torch.randn(1, 3, size, size)
    torch.onnx.export(Wrap().eval(), (x,), str(out_dir / fname), input_names=["pixel_values"],
                      output_names=["logits"], dynamic_axes={"pixel_values": {0: "n"},
                      "logits": {0: "n"}}, opset_version=17, dynamo=False)  # fmt: skip
    import onnxruntime as ort

    sess = ort.InferenceSession(str(out_dir / fname))
    with torch.inference_mode():
        ref = Wrap()(x).numpy()
    got = sess.run(None, {"pixel_values": x.numpy()})[0]
    diff = float(np.abs(ref - got).max())
    print(f"exported {fname}: max |diff| vs PyTorch {diff:.2e}")
    tst = report["test"]["native"]
    spec = {
        "name": c.name, "repo": c.repo, "license": c.license, "file": fname,
        "tau_lo": report["thresholds"]["tau_lo"], "tau_hi": report["thresholds"]["tau_hi"],
        "fpr_at_tau_lo": 0.05, "fpr_at_tau_hi": 0.01,
        "metrics": {
            "val_auc_normalised": report["candidates"][c.name]["normalised"]["auc"],
            "test_auc_native": tst["auc"],
            "test_auc_normalised": report["test"]["normalised"]["auc"],
            "test_tpr_at_tau_hi": tst["at_frozen"]["tau_hi"]["tpr"],
            "test_fpr_at_tau_hi": tst["at_frozen"]["tau_hi"]["fpr"],
            "test_tpr_at_tau_lo": tst["at_frozen"]["tau_lo"]["tpr"],
            "test_fpr_at_tau_lo": tst["at_frozen"]["tau_lo"]["fpr"],
            "dataset": "Defactify (MS COCO vs SD2.1/SDXL/SD3/DALL-E3/Midjourney v6)",
        },
        "onnx_max_abs_diff": diff,
    }  # fmt: skip
    if c.kind == "commfor":
        spec.update({"size": 384, "resize": "shortest_crop", "pre_resize": 440,
                     "mean": meta["mean"], "std": meta["std"], "single_logit": True})  # fmt: skip
    else:
        proc = meta.get("processor", {})
        spec.update({"size": size, "resize": "squash", "fake_index": meta["fake_index"],
                     "mean": proc.get("image_mean", [0.5, 0.5, 0.5]),
                     "std": proc.get("image_std", [0.5, 0.5, 0.5])})  # fmt: skip
    (ROOT / "config" / "aigen_model.json").write_text(json.dumps(spec, indent=1))
    print("wrote config/aigen_model.json")


if __name__ == "__main__":
    main()
