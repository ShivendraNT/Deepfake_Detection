"""Voice-clone benchmark (docs/VOICE_DEEPFAKE.md): gate -> selection -> thresholds -> test once.

    python -m research.voice.bench            # every stage; cached, so a re-run resumes

1. Channel copies of val/test clips: clean, opus16 (libopus 16 kbps), gsm (GSM 06.10, 8 kHz).
2. Our model: XLS-R layer-7 mean embeddings; logistic regression on ASVspoof 2019 LA train
   with C chosen by speaker-grouped 5-fold CV (train only).
3. Gate: every candidate scored on val/clean; test sets only for val AUC >= 0.70.
4. Selection (val/opus16, paired speaker bootstrap) and thresholds (1% / 5% FPR on val
   bonafide per condition, max kept) -> results/voice_selection.json.
5. Test sets scored once -> results/voice_benchmark.{json,md}.
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np  # provenance: seeded-resampling-ok

from research.metrics import auroc, threshold_at_fpr
from research.video.stats import cluster_ci, cluster_paired_diff, eer, wilson
from research.voice.data import DATA, ROOT, SEED, Split, load
from research.voice.models import BY_NAME, CANDIDATES, hf_classifier, xlsr_features

CONDITIONS = ("clean", "opus16", "gsm")
TEST_CONDITIONS = ("clean", "opus16")  # gsm only for the shipped model (CPU budget, §4)
GATE_N = 500
EVAL_SPLITS = ("val", "test_itw", "test_asv")
GATE_AUC = 0.70
OURS = "satya_xlsr_l7"
SELECT_CONDITION = "opus16"
C_GRID = (0.01, 0.1, 1.0, 10.0)
SCORES, FEATS = DATA / "scores", DATA / "feats"
RESULTS = ROOT / "results"


# ----------------------------------------------------------------------------- channels
def channel(x: np.ndarray, cond: str) -> np.ndarray:
    from research.seal.channels import _ffmpeg_roundtrip, opus

    if cond == "clean":
        return x
    if cond == "opus16":
        y = opus(x.astype(np.float64), 16)
    elif cond == "gsm":
        y = _ffmpeg_roundtrip(
            x.astype(np.float64), ["-ar", "8000", "-ac", "1", "-c:a", "libgsm"], "wav"
        )
    else:
        raise ValueError(cond)
    return y[: len(x)].astype(np.float32)


def audio_for(split: str, cond: str) -> list[np.ndarray]:
    """The split's clips through the channel (cached as int16 next to the clean clips)."""
    cache = DATA / "clips" / f"{split}__{cond}.npz"
    clean = load(split).audio
    if cond == "clean":
        return clean
    if not cache.exists():
        out = [channel(x, cond) for x in clean]
        lens = np.array([len(x) for x in out])
        np.savez(
            cache,
            audio=np.round(np.clip(np.concatenate(out), -1, 1) * 32767).astype(np.int16),
            offsets=np.r_[0, np.cumsum(lens)],
        )
    z = np.load(cache)
    off, raw = z["offsets"], z["audio"]  # read each array once
    return [raw[off[i] : off[i + 1]].astype(np.float32) / 32768.0 for i in range(len(off) - 1)]


# ----------------------------------------------------------------------------- scoring
def features(split: str, cond: str, embed=None) -> np.ndarray:
    f = FEATS / f"{split}__{cond}.npy"
    if not f.exists():
        embed = embed or xlsr_features()
        t0 = time.time()
        clips = audio_for(split, cond)
        out = np.stack([embed(x) for x in clips])
        f.parent.mkdir(parents=True, exist_ok=True)
        np.save(f, out)
        print(f"xlsr features {split}/{cond}: {len(clips)} clips, "
              f"{1000 * (time.time() - t0) / len(clips):.0f} ms/clip", flush=True)  # fmt: skip
    return np.load(f)


def hf_scores(name: str, split: str, cond: str, idx: np.ndarray | None = None) -> np.ndarray:
    f = SCORES / name / (f"{split}__{cond}.npy" if idx is None else f"{split}_sub__{cond}.npy")
    if not f.exists():
        fn = hf_classifier(name)
        t0 = time.time()
        clips = audio_for(split, cond)
        clips = clips if idx is None else [clips[i] for i in idx]
        out = np.array([fn(x) for x in clips], np.float32)
        f.parent.mkdir(parents=True, exist_ok=True)
        np.save(f, out)
        print(f"{name} {split}/{cond}: {1000 * (time.time() - t0) / len(clips):.0f} ms/clip",
              flush=True)  # fmt: skip
    return np.load(f)


def hf_gate(name: str, gi: np.ndarray) -> np.ndarray:
    """Gate scores on the val subset only (cached separately: cheap for models that fail)."""
    f = SCORES / name / "val_gate__clean.npy"
    full = SCORES / name / "val__clean.npy"
    if full.exists():
        return np.load(full)[gi]
    if not f.exists():
        fn = hf_classifier(name)
        clips = audio_for("val", "clean")
        t0 = time.time()
        out = np.array([fn(clips[i]) for i in gi], np.float32)
        f.parent.mkdir(parents=True, exist_ok=True)
        np.save(f, out)
        print(f"{name} gate: {1000 * (time.time() - t0) / len(gi):.0f} ms/clip", flush=True)
    return np.load(f)


def fit_ours() -> dict:
    """C by speaker-grouped 5-fold CV on train; standardise + LR; saved for export."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.preprocessing import StandardScaler

    tr = load("train")
    x, y, g = features("train", "clean"), tr.labels, tr.speakers
    folds = list(StratifiedGroupKFold(5, shuffle=True, random_state=SEED).split(x, y, g))
    grid = {}
    for c in C_GRID:
        aucs = []
        for a, b in folds:
            sc = StandardScaler().fit(x[a])
            lr = LogisticRegression(C=c, max_iter=5000, class_weight="balanced")
            lr.fit(sc.transform(x[a]), y[a])
            aucs.append(auroc(y[b].tolist(), lr.decision_function(sc.transform(x[b])).tolist()))
        grid[c] = aucs
    best = max(grid, key=lambda c: float(np.mean(grid[c])))
    sc = StandardScaler().fit(x)
    lr = LogisticRegression(C=best, max_iter=5000, class_weight="balanced").fit(sc.transform(x), y)
    head = {
        "mean": sc.mean_.tolist(), "scale": sc.scale_.tolist(),
        "coef": lr.coef_.ravel().tolist(), "intercept": float(lr.intercept_[0]), "C": best,
        "cv_auc_mean": round(float(np.mean(grid[best])), 4),
        "cv_auc_sd": round(float(np.std(grid[best], ddof=1)), 4),
        "grid": {str(c): round(float(np.mean(v)), 4) for c, v in grid.items()},
    }  # fmt: skip
    (DATA / "ours_head.json").write_text(json.dumps(head))
    return head


def ours_scores(split: str, cond: str, head: dict) -> np.ndarray:
    z = (features(split, cond) - np.array(head["mean"])) / np.array(head["scale"])
    return z @ np.array(head["coef"]) + head["intercept"]


def scores(name: str, split: str, cond: str, head: dict, idx: np.ndarray | None = None):
    if name == OURS:
        s = ours_scores(split, cond, head)
        return s if idx is None else s[idx]
    return hf_scores(name, split, cond, idx)


def test_subset(split: str, sp: Split) -> np.ndarray:
    """Seeded test subset for a shipped off-the-shelf model (amendment 2, CPU): 1,000
    In-the-Wild clips; 300 bonafide + 30 per attack of ASVspoof eval."""
    rng = np.random.default_rng(SEED + 1)
    if split == "test_itw":
        return np.sort(rng.choice(len(sp.labels), size=min(1000, len(sp.labels)), replace=False))
    groups = [np.flatnonzero(sp.labels == 0)] + [
        np.flatnonzero(sp.attacks == a) for a in sorted(set(sp.attacks.tolist()) - {"-"})
    ]
    sizes = [300] + [30] * (len(groups) - 1)
    picked = [
        rng.choice(g, size=min(n, len(g)), replace=False)
        for g, n in zip(groups, sizes, strict=True)
    ]
    return np.sort(np.concatenate(picked))


def subset(sp: Split, idx: np.ndarray) -> Split:
    return Split(sp.ids[idx], sp.labels[idx], sp.speakers[idx], sp.attacks[idx],
                 [sp.audio[i] for i in idx])  # fmt: skip


# ----------------------------------------------------------------------------- metrics
def _auc(y: np.ndarray, s: np.ndarray) -> float:
    return auroc(y.tolist(), s.tolist())


def block(sp: Split, s: np.ndarray, tau: dict[str, float] | None) -> dict:
    out: dict = {
        "n_bonafide": int((sp.labels == 0).sum()),
        "n_spoof": int(sp.labels.sum()),
        "auc": cluster_ci(_auc, sp.labels, s, sp.speakers),
        "eer": cluster_ci(eer, sp.labels, s, sp.speakers),
    }
    if tau:
        for k, t in tau.items():
            out[f"tpr@{k}"] = wilson(int((s[sp.labels == 1] >= t).sum()), int(sp.labels.sum()))
            out[f"fpr@{k}"] = wilson(
                int((s[sp.labels == 0] >= t).sum()), int((sp.labels == 0).sum())
            )
    return out


def gate_index(val: Split) -> np.ndarray:
    """Seeded 500-clip subset of val for the gate (same clips for every candidate)."""
    rng = np.random.default_rng(SEED)
    return np.sort(rng.choice(len(val.labels), size=min(GATE_N, len(val.labels)), replace=False))


def warm(argv: list[str]) -> None:
    """Fill caches in parallel processes: `ours SPLIT...` or `hf NAME SPLIT COND...`."""
    import torch

    torch.set_num_threads(2)
    if argv[0] == "ours":
        embed = xlsr_features()
        for split in argv[1:]:
            for cond in ("clean",) if split == "train" else CONDITIONS:
                features(split, cond, embed)
    elif argv[0] == "gate":
        val = load("val")
        for name in argv[1:]:
            hf_gate(name, gate_index(val))
    else:
        name, split, *conds = argv[1:]
        for cond in conds:
            hf_scores(name, split, cond)


def main() -> None:
    if len(sys.argv) > 2 and sys.argv[1] == "--warm":
        warm(sys.argv[2:])
        return
    head = fit_ours()
    print("ours", {k: head[k] for k in ("C", "cv_auc_mean", "cv_auc_sd", "grid")}, flush=True)
    val = load("val")
    report: dict = {"seed": SEED, "conditions": list(CONDITIONS), "ours_fit": {
        k: head[k] for k in ("C", "cv_auc_mean", "cv_auc_sd", "grid")}, "gate": {}}  # fmt: skip
    # 1. gate on val/clean
    passed = []
    gi = gate_index(val)
    for c in CANDIDATES:
        s_gate = scores(c.name, "val", "clean", head)[gi] if c.name == OURS else hf_gate(c.name, gi)
        auc = cluster_ci(_auc, val.labels[gi], s_gate, val.speakers[gi])
        report["gate"][c.name] = auc
        print("gate", c.name, auc, flush=True)
        if auc["value"] >= GATE_AUC:
            passed.append(c.name)
    # 2. selection on val/opus16 among eligible gate-passers
    sel: dict = {"rule": "replace ours only if val AUC (opus16) gain > 1 bootstrap SE",
                 "candidates": {}, "decision": OURS}  # fmt: skip
    s_ours = scores(OURS, "val", SELECT_CONDITION, head)
    best_gain = 0.0
    for name in passed:
        if name == OURS or not BY_NAME[name].eligible:
            continue
        d = cluster_paired_diff(_auc, val.labels, scores(name, "val", SELECT_CONDITION, head),
                                s_ours, val.speakers)  # fmt: skip
        sel["candidates"][name] = d
        if d["value"] > d["se"] and d["value"] > best_gain:
            best_gain, sel["decision"] = d["value"], name
    chosen = sel["decision"]
    # 3. thresholds for the chosen model: 1% / 5% FPR on val bonafide, per condition, max kept
    per = {}
    for cond in CONDITIONS:
        sv = scores(chosen, "val", cond, head)[val.labels == 0].tolist()
        per[cond] = {"tau_hi": float(threshold_at_fpr(sv, 0.01)),
                     "tau_lo": float(threshold_at_fpr(sv, 0.05))}  # fmt: skip
    tau = {"tau_hi": max(v["tau_hi"] for v in per.values()),
           "tau_lo": max(v["tau_lo"] for v in per.values())}  # fmt: skip
    sel.update({"model": chosen, "thresholds_logit": tau, "per_condition": per})
    (RESULTS / "voice_selection.json").write_text(json.dumps(sel, indent=1) + "\n")
    print("selection", json.dumps(sel, indent=1), flush=True)
    # 4. test once
    report["selection"] = sel
    report["results"] = {}
    # Amendment 2 (CPU): test sets for the shipped model only; other gate-passers report the
    # selection condition on val. A shipped off-the-shelf model is tested on seeded subsets.
    for name in passed:
        r = {}
        shipped = name == chosen
        for split in EVAL_SPLITS if shipped else ("val",):
            sp = load(split)
            idx = test_subset(split, sp) if shipped and name != OURS and split != "val" else None
            sp = sp if idx is None else subset(sp, idx)
            if not shipped:
                conds: tuple[str, ...] = (SELECT_CONDITION,)
            elif name == OURS or split == "val":
                conds = CONDITIONS
            else:
                conds = TEST_CONDITIONS
            for cond in conds:
                s = scores(name, split, cond, head, idx)
                r[f"{split}/{cond}"] = block(sp, s, tau if shipped else None)
                if split == "test_asv" and cond == "clean":
                    per_attack = {}
                    for a in sorted(set(sp.attacks.tolist()) - {"-"}):
                        m = (sp.attacks == a) | (sp.labels == 0)  # this attack vs all bonafide
                        per_attack[a] = round(_auc(sp.labels[m], s[m]), 4)
                    r["per_attack"] = per_attack
        report["results"][name] = r
        print(
            "tested", name, {k: v["auc"]["value"] for k, v in r.items() if "auc" in v}, flush=True
        )
    (RESULTS / "voice_benchmark.json").write_text(json.dumps(report, indent=1) + "\n")
    from research.voice.report import render

    (RESULTS / "voice_benchmark.md").write_text(render(report))
    print((RESULTS / "voice_benchmark.md").read_text())


if __name__ == "__main__":
    sys.exit(main())
