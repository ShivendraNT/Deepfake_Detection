"""Train the blend-artifact CNN on REAL faces + self-blended pseudo-fakes, export ONNX.

    python -m research.video.train_sbi --epochs 12 --threads 2

Backbone: EfficientNet-B0 (ImageNet weights, timm), 224 px, stem + first three stages frozen
(CPU budget). Model selection: AUC on val reals vs. seeded self-blends of the SAME val reals.
No real deepfake is read at any point, so every deepfake test number is an unseen-method
number for this model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import queue
import threading
import time

import numpy as np  # provenance: seeded-resampling-ok

from research.video.data import DATA, ROOT, SEED
from research.video.sbi import common_augment, self_blend
from research.video.sbi_prep import OUT as PREP
from research.video.sbi_prep import load_prepped

MODEL_OUT = ROOT / "models" / "video"
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


def to_tensor_batch(imgs: list[np.ndarray]):
    import torch

    x = np.stack(imgs).astype(np.float32) / 255.0
    x = (x - MEAN) / STD
    return torch.from_numpy(x.transpose(0, 3, 1, 2).copy()).contiguous(
        memory_format=torch.channels_last
    )


def crop224(img: np.ndarray, lms: np.ndarray, rng: np.random.Generator | None) -> np.ndarray:
    from satyapan.video.observe import face_crop

    if rng is None:
        return face_crop(img, lms)
    jitter = lms + rng.uniform(-0.03, 0.03, 2) * img.shape[1]
    return face_crop(img, jitter, margin=float(rng.uniform(1.2, 1.4)))


def load_split(split: str) -> tuple[list[np.ndarray], list[np.ndarray]]:
    imgs, lms = [], []
    for path in sorted(PREP.glob("*.npz")):
        crops, lm, sp = load_prepped(path)
        if sp == split:
            imgs += crops
            lms += list(lm)
    return imgs, lms


def build_model(pretrained: bool = True):
    import timm

    m = timm.create_model("efficientnet_b0", pretrained=pretrained, num_classes=1)
    frozen = [m.conv_stem, m.bn1, *m.blocks[:3]]
    for mod in frozen:
        for p in mod.parameters():
            p.requires_grad = False
    return m, frozen


def auc(y: np.ndarray, s: np.ndarray) -> float:
    order = np.argsort(s)
    ranks = np.empty(len(s))
    ranks[order] = np.arange(1, len(s) + 1)
    pos = y == 1
    n1, n0 = pos.sum(), (~pos).sum()
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def predict(model, imgs: list[np.ndarray], batch: int = 64) -> np.ndarray:
    import torch

    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(imgs), batch):
            out.append(model(to_tensor_batch(imgs[i : i + batch])).squeeze(1).numpy())
    return np.concatenate(out)


def main() -> None:
    import torch

    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--steps", type=int, default=190, help="batches per epoch")
    ap.add_argument("--batch", type=int, default=32, help="half real, half self-blended")
    ap.add_argument("--lr", type=float, default=4e-4)
    ap.add_argument("--threads", type=int, default=2)
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED)

    tr_imgs, tr_lms = load_split("sbi_train")
    va_imgs, va_lms = load_split("val")
    print(f"train base frames {len(tr_imgs)}, val base frames {len(va_imgs)}", flush=True)
    vrng = np.random.default_rng(SEED + 1)  # fixed validation pseudo-fakes
    val_x = [crop224(im, lm, None) for im, lm in zip(va_imgs, va_lms, strict=True)]
    val_x += [
        crop224(self_blend(im, lm, vrng), lm, None) for im, lm in zip(va_imgs, va_lms, strict=True)
    ]
    val_y = np.array([0] * len(va_imgs) + [1] * len(va_imgs))

    model, frozen = build_model()
    model = model.to(memory_format=torch.channels_last)
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=1e-4)
    total = args.epochs * args.steps
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=args.lr, total_steps=total, pct_start=0.1
    )
    MODEL_OUT.mkdir(parents=True, exist_ok=True)
    best, history = -1.0, []
    half = args.batch // 2

    def make_batch() -> tuple[list[np.ndarray], list[float]]:
        idx = rng.integers(0, len(tr_imgs), half)
        xs, ys = [], []
        for i in idx:
            im, lm = tr_imgs[i], tr_lms[i]
            xs.append(common_augment(crop224(im, lm, rng), rng))
            ys.append(0.0)
            xs.append(common_augment(crop224(self_blend(im, lm, rng), lm, rng), rng))
            ys.append(1.0)
        return xs, ys

    # One producer thread (deterministic order: a single thread owns `rng`).
    batches: queue.Queue[tuple[list[np.ndarray], list[float]]] = queue.Queue(maxsize=4)

    def producer() -> None:
        for _ in range(total):
            batches.put(make_batch())

    threading.Thread(target=producer, daemon=True).start()
    for epoch in range(args.epochs):
        model.train()
        for mod in frozen:
            mod.eval()  # keep frozen BatchNorm statistics
        t0, losses = time.time(), []
        for _ in range(args.steps):
            xs, ys = batches.get()
            logits = model(to_tensor_batch(xs)).squeeze(1)
            loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, torch.tensor(ys))
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            losses.append(float(loss))
        scores = predict(model, val_x)
        val_auc = auc(val_y, scores)
        history.append(
            {
                "epoch": epoch + 1,
                "loss": float(np.mean(losses)),
                "val_sbi_auc": val_auc,
                "seconds": round(time.time() - t0, 1),
            }
        )
        print(json.dumps(history[-1]), flush=True)
        if val_auc > best:
            best = val_auc
            torch.save(model.state_dict(), MODEL_OUT / "blend_b0.pt")
    model.load_state_dict(torch.load(MODEL_OUT / "blend_b0.pt"))
    model.eval()
    onnx_path = MODEL_OUT / "blend_b0.onnx"
    torch.onnx.export(
        model,
        torch.zeros(1, 3, 224, 224),
        str(onnx_path),
        input_names=["image"],
        output_names=["logit"],
        dynamic_axes={"image": {0: "n"}, "logit": {0: "n"}},
        opset_version=17,
        dynamo=False,
    )
    digest = hashlib.sha256(onnx_path.read_bytes()).hexdigest()
    meta = {
        "model": "efficientnet_b0 (timm, ImageNet init), stem+3 stages frozen",
        "input": "RGB 224x224, ImageNet mean/std, face_crop(margin=1.3)",
        "train": "FF++ c23 sbi_train reals (480 videos x 16 frames) + self-blends",
        "selection": "best val AUC, FF++ val reals vs seeded self-blends (no deepfakes)",
        "seed": SEED,
        "args": vars(args),
        "history": history,
        "best_val_sbi_auc": best,
        "onnx_sha256": digest,
    }
    (MODEL_OUT / "blend_b0.json").write_text(json.dumps(meta, indent=1))
    (DATA / "logs" / "train_sbi_final.json").write_text(json.dumps(meta, indent=1))
    print("exported", onnx_path, digest)


if __name__ == "__main__":
    main()
