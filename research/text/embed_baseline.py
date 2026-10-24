"""Transformer baseline for the text benchmark: multilingual sentence embeddings + LR.

    python -m research.text.embed_baseline     # -> results/text_embed_baseline.{json,md}

"Why TF-IDF and not a transformer?" Same table, same splits, same protocol as bench.py, with
the features swapped for `intfloat/multilingual-e5-small` (MIT, ~100 languages incl. Hindi
and the other Indian scripts; revision pinned) mean-pooled sentence embeddings (first 256
tokens, "query: " prefix as its card asks). C by the same grouped 5-fold CV on train, each
dataset weighted equally, thresholds on val, test once, leave-one-dataset-out, and the
combined obfuscation attack with and without our de-obfuscation layer.
"""

from __future__ import annotations

import json

import numpy as np  # provenance: seeded-resampling-ok
import pandas as pd

from research.metrics import auroc
from research.text.attacks import attack
from research.text.bench import RESULTS, dataset_weights, evaluate, thresholds
from research.text.data import DATA, SEED, SOURCES
from research.video.stats import wilson
from satyapan.textrisk.normalize import deobfuscate

REPO = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
MAX_TOKENS = 256
C_GRID = (0.1, 1.0, 10.0, 100.0)


class Embedder:
    def __init__(self, threads: int = 1) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        torch.set_num_threads(threads)
        self.tok = AutoTokenizer.from_pretrained(REPO, revision=REVISION)
        self.net = AutoModel.from_pretrained(REPO, revision=REVISION).eval()

    def __call__(self, texts: list[str], batch: int = 32) -> np.ndarray:
        import torch

        out = []
        for i in range(0, len(texts), batch):
            enc = self.tok(
                ["query: " + t[:4000] for t in texts[i : i + batch]],
                max_length=MAX_TOKENS, truncation=True, padding=True, return_tensors="pt",
            )  # fmt: skip
            with torch.inference_mode():
                h = self.net(**enc).last_hidden_state
            m = enc["attention_mask"].unsqueeze(-1).float()
            e = (h * m).sum(1) / m.sum(1).clamp(min=1.0)
            out.append(torch.nn.functional.normalize(e, dim=1).numpy())
            if (i // batch) % 100 == 0:
                print(f"embedded {i + len(texts[i : i + batch])}/{len(texts)}", flush=True)
        return np.concatenate(out).astype(np.float32)


def fit(x: np.ndarray, y: np.ndarray, c: float, w: np.ndarray | None):
    from sklearn.linear_model import LogisticRegression

    lr = LogisticRegression(C=c, class_weight="balanced", max_iter=3000)
    lr.fit(x, y, sample_weight=w)
    return lr


def cv_c(x: np.ndarray, y: np.ndarray, g: np.ndarray, w: np.ndarray) -> dict:
    from sklearn.model_selection import StratifiedGroupKFold

    folds = list(StratifiedGroupKFold(5, shuffle=True, random_state=SEED).split(x, y, g))
    grid = {}
    for c in C_GRID:
        grid[c] = [
            auroc(y[va].tolist(), fit(x[tr], y[tr], c, w[tr]).decision_function(x[va]).tolist())
            for tr, va in folds
        ]
    best = max(grid, key=lambda c: float(np.mean(grid[c])))
    return {
        "best_C": best,
        "cv_auc_mean": round(float(np.mean(grid[best])), 4),
        "cv_auc_sd": round(float(np.std(grid[best], ddof=1)), 4),
        "grid": {str(c): round(float(np.mean(v)), 4) for c, v in grid.items()},
    }


def prob(lr, x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(lr.decision_function(x), -30, 30)))


def main() -> None:
    df = pd.read_parquet(DATA / "table.parquet").reset_index(drop=True)
    cache = DATA / f"emb_{REPO.split('/')[1]}_{REVISION[:8]}.npy"
    emb = Embedder()
    if cache.exists():
        x = np.load(cache)
    else:
        x = emb(df.text.tolist())
        np.save(cache, x)
    y, g = df.label.to_numpy(int), df.group.to_numpy(str)
    tr, va, te = (df.split == s for s in ("train", "val", "test"))
    tr, va, te = tr.to_numpy(), va.to_numpy(), te.to_numpy()
    w = dataset_weights(df.dataset)
    cv = cv_c(x[tr], y[tr], g[tr], w[tr])
    union = fit(x[tr], y[tr], cv["best_C"], w[tr])
    s = prob(union, x)
    thr = thresholds(y[va], s[va])
    report: dict[str, object] = {
        "model": f"{REPO}@{REVISION}", "max_tokens": MAX_TOKENS, "cv": cv,
        "thresholds": thr, "per_dataset": {},
    }  # fmt: skip
    print("union", cv, thr, flush=True)
    for src in SOURCES:
        d = (df.dataset == src.name).to_numpy()
        dte = d & te
        block = {"union": evaluate(y[dte], s[dte], g[dte], thr)}
        other = tr & ~d
        lodo = fit(x[other], y[other], cv["best_C"], dataset_weights(df.dataset[other]))
        s_o = prob(lodo, x)
        block["lodo"] = evaluate(y[dte], s_o[dte], g[dte], thresholds(y[va & ~d], s_o[va & ~d]))
        report["per_dataset"][src.name] = block  # type: ignore[index]
        print(src.name, {k: v.get("auc", {}).get("value") for k, v in block.items()}, flush=True)
    # The combined obfuscation attack (same seeds as bench.py), raw and de-obfuscated input.
    fraud = [i for i in np.flatnonzero(te) if y[i] == 1]
    attacked = [attack(df.text.iloc[i], "combined", f"{SEED}:combined:{i}") for i in fraud]
    rob = {}
    for tag, texts in (("raw", attacked), ("deobfuscated", [deobfuscate(t) for t in attacked])):
        sf = prob(union, emb(texts))
        rob[tag] = wilson(int((sf >= thr["tau_hi"]).sum()), len(sf))
        print("attack combined", tag, rob[tag], flush=True)
    report["robustness_combined"] = rob
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "text_embed_baseline.json").write_text(json.dumps(report, indent=1) + "\n")
    (RESULTS / "text_embed_baseline.md").write_text(render(report))
    print(render(report))


def _ci(x: object) -> str:
    if not isinstance(x, dict) or "value" not in x:
        return "n/a"
    return f"{x['value']:.3f} [{x['low']:.3f}, {x['high']:.3f}]"


def _rate(w: object) -> str:
    if not isinstance(w, dict) or w.get("value") is None:
        return "n/a"
    lo, hi = w["ci95"]
    return f"{100 * w['value']:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]"


def render(r: dict) -> str:
    out = [
        "# Transformer baseline: multilingual-e5-small embeddings + LR (same protocol)",
        "",
        f"Model `{r['model']}`, first {r['max_tokens']} tokens. C = {r['cv']['best_C']} by "
        f"grouped CV (AUC {r['cv']['cv_auc_mean']} ± {r['cv']['cv_auc_sd']}); "
        f"tau_hi = {r['thresholds']['tau_hi']:.4f} on val.",
        "",
        "| Dataset | union AUC | union TPR @ tau_hi | union FPR @ tau_hi | LODO AUC |",
        "|---|---|---|---|---|",
    ]
    for name, b in r["per_dataset"].items():
        u = b["union"]
        out.append(
            f"| {name} | {_ci(u.get('auc'))} | {_rate(u.get('tpr@tau_hi'))} | "
            f"{_rate(u.get('fpr@tau_hi'))} | {_ci(b['lodo'].get('auc'))} |"
        )
    rob = r["robustness_combined"]
    out += [
        "",
        f"Combined obfuscation attack, TPR @ tau_hi: raw input {_rate(rob['raw'])}; "
        f"after our de-obfuscation {_rate(rob['deobfuscated'])}.",
    ]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    main()
