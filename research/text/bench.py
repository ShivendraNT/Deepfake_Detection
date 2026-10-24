"""Text benchmark: scam / phishing / fraud text detection on open datasets.

    python -m research.text.data        # download (sha256-pinned), dedup, leakage-safe splits
    python -m research.text.bench       # CV -> frozen thresholds -> one test run -> results/

Models (docs/TEXT_BENCHMARK.md):
  asks_frozen   the frozen ask lexicon v1.0 (zero-shot; score = number of distinct ask types)
  asks_product  context filter + lexicon + live phrasebook, as Satya runs it (zero-shot)
  tfidf_spec    hashed TF-IDF + logistic regression trained on ONE dataset (specialist)
  tfidf_union   the same model trained on the union of all training splits (ships in Satya)
  tfidf_lodo    leave-one-dataset-out: trained on all OTHER datasets, tested on the held-out one
  ..._raw       the union model without the de-obfuscation layer (robustness ablation)

Protocol: C chosen by 5-fold GroupKFold CV on train (groups = message templates); decision
thresholds fixed on val (tau_hi = 1% FPR, tau_lo = 5% FPR on legitimate val texts, and the
max-F1 point); every test split is scored once. Intervals: 95% bootstrap (2,000 resamples,
template clusters) for AUC/AP; Wilson for rates. All randomness seeded.
"""

from __future__ import annotations

import hashlib
import json
from multiprocessing import Pool

import numpy as np  # provenance: seeded-resampling-ok
import pandas as pd

from research.metrics import auroc, threshold_at_fpr
from research.text.attacks import ATTACKS, attack
from research.text.data import DATA, ROOT, SEED, SOURCES
from research.video.stats import cluster_ci, wilson
from satyapan.textrisk.features import N_FEATURES, hashed_tf

C_GRID = (0.5, 2.0, 8.0, 32.0)
RESULTS = ROOT / "results"


# ----------------------------------------------------------------------------- features
def _tf(args: tuple[str, bool]) -> dict[int, float]:
    return hashed_tf(args[0], args[1])


def featurize(texts: list[str], normalise: bool = True, workers: int = 2):
    import scipy.sparse as sp

    with Pool(workers) as pool:
        rows = pool.map(_tf, [(t, normalise) for t in texts], chunksize=64)
    indptr, indices, data = [0], [], []
    for r in rows:
        indices.extend(r.keys())
        data.extend(r.values())
        indptr.append(len(indices))
    return sp.csr_matrix(
        (np.array(data, np.float32), np.array(indices, np.int64), np.array(indptr, np.int64)),
        shape=(len(rows), N_FEATURES),
    )


def idf_of(x) -> np.ndarray:
    df = np.asarray((x != 0).sum(axis=0)).ravel()
    n = x.shape[0]
    idf = (np.log((1 + n) / (1 + df)) + 1.0).astype(np.float32)
    idf[df == 0] = 0.0
    return idf


def transform(x, idf: np.ndarray):
    from sklearn.preprocessing import normalize

    return normalize(x.multiply(idf).tocsr(), norm="l2", copy=False)


def fit(x, y: np.ndarray, c: float, weights: np.ndarray | None = None):
    from sklearn.linear_model import LogisticRegression

    lr = LogisticRegression(C=c, solver="liblinear", class_weight="balanced", max_iter=2000)
    lr.fit(x, y, sample_weight=weights)
    return lr


def decision(lr, x) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(lr.decision_function(x), -30, 30)))


def dataset_weights(ds: pd.Series) -> np.ndarray:
    """Each dataset weighs the same in the union model, whatever its size."""
    counts = ds.value_counts()
    return np.array([len(ds) / (len(counts) * counts[d]) for d in ds], np.float64)


def cv_choose_c(x, y: np.ndarray, groups: np.ndarray, weights: np.ndarray | None) -> dict:
    from sklearn.model_selection import StratifiedGroupKFold

    folds = list(StratifiedGroupKFold(5, shuffle=True, random_state=SEED).split(x, y, groups))
    grid: dict[float, list[float]] = {}
    for c in C_GRID:
        aucs = []
        for tr, va in folds:
            idf = idf_of(x[tr])
            lr = fit(transform(x[tr], idf), y[tr], c, None if weights is None else weights[tr])
            aucs.append(auroc(y[va].tolist(), decision(lr, transform(x[va], idf)).tolist()))
        grid[c] = aucs
    best = max(grid, key=lambda c: float(np.mean(grid[c])))
    return {
        "best_C": best,
        "cv_auc_mean": round(float(np.mean(grid[best])), 4),
        "cv_auc_sd": round(float(np.std(grid[best], ddof=1)), 4),
        "grid": {str(c): round(float(np.mean(v)), 4) for c, v in grid.items()},
    }


# ----------------------------------------------------------------------------- metrics
def thresholds(y_val: np.ndarray, s_val: np.ndarray) -> dict[str, float]:
    neg = s_val[y_val == 0].tolist()
    best_f1, best_t = -1.0, 0.5
    for t in np.unique(s_val):
        pred = s_val >= t
        tp = float((pred & (y_val == 1)).sum())
        f1 = 2 * tp / max(1.0, pred.sum() + (y_val == 1).sum())
        if f1 > best_f1:
            best_f1, best_t = f1, float(t)
    return {
        "tau_hi": float(threshold_at_fpr(neg, 0.01)),
        "tau_lo": float(threshold_at_fpr(neg, 0.05)),
        "tau_f1": best_t,
    }


def evaluate(
    y: np.ndarray, s: np.ndarray, groups: np.ndarray, thr: dict[str, float] | None
) -> dict[str, object]:
    from sklearn.metrics import average_precision_score

    out: dict[str, object] = {"n": int(len(y)), "n_fraud": int(y.sum())}
    if 0 < y.sum() < len(y):
        out["auc"] = cluster_ci(lambda a, b: auroc(a.tolist(), b.tolist()), y, s, groups)
        out["ap"] = cluster_ci(lambda a, b: float(average_precision_score(a, b)), y, s, groups)
    if thr:
        for name in ("tau_hi", "tau_f1"):
            pred = s >= thr[name]
            tp, fp = int((pred & (y == 1)).sum()), int((pred & (y == 0)).sum())
            fn = int((~pred & (y == 1)).sum())
            out[f"tpr@{name}"] = wilson(tp, int(y.sum()))
            out[f"fpr@{name}"] = wilson(fp, int((y == 0).sum()))
            out[f"f1@{name}"] = round(2 * tp / max(1, 2 * tp + fp + fn), 4)
    return out


# ----------------------------------------------------------------------------- lexicon
def ask_count(text: str, product: bool) -> int:
    from satyapan.asks.extractor import extract_asks

    if not product:
        return len({s.ask_type for s in extract_asks(text)})
    from satyapan.asks.phrasebook import extract_live_asks
    from satyapan.context import strip_context

    return len({s.ask_type for s in extract_live_asks(strip_context(text).cleaned)})


def _asks(args: tuple[str, bool]) -> int:
    return ask_count(*args)


# ----------------------------------------------------------------------------- main
def main() -> None:
    df = pd.read_parquet(DATA / "table.parquet").reset_index(drop=True)
    names = [s.name for s in SOURCES]
    report: dict[str, object] = {"seed": SEED, "datasets": names, "c_grid": list(C_GRID)}
    print("featurising", len(df), "texts", flush=True)
    x_all = featurize(df.text.tolist(), True, workers=2)
    y_all = df.label.to_numpy(int)
    g_all = df.group.to_numpy(str)
    is_tr, is_va, is_te = (df.split == s for s in ("train", "val", "test"))

    # ---- union model (ships in Satya)
    tr = is_tr.to_numpy()
    w_tr = dataset_weights(df.dataset[tr])
    cv = cv_choose_c(x_all[tr], y_all[tr], g_all[tr], w_tr)
    idf = idf_of(x_all[tr])
    union = fit(transform(x_all[tr], idf), y_all[tr], cv["best_C"], w_tr)
    s_all = decision(union, transform(x_all, idf))
    va = is_va.to_numpy()
    thr_union = thresholds(y_all[va], s_all[va])
    report["union"] = {"cv": cv, "thresholds": thr_union, "per_dataset": {}}
    print("union", cv, thr_union, flush=True)

    # ---- zero-shot ask lexicon (frozen research lexicon and the product path)
    with Pool(2) as pool:
        df["asks_frozen"] = pool.map(_asks, [(t, False) for t in df.text], chunksize=64)
        df["asks_product"] = pool.map(_asks, [(t, True) for t in df.text], chunksize=64)

    per: dict[str, object] = {}
    for name in names:
        d = (df.dataset == name).to_numpy()
        te, dva, dtr = d & is_te.to_numpy(), d & va, d & tr
        y, g = y_all[te], g_all[te]
        block: dict[str, object] = {}
        block["tfidf_union"] = evaluate(y, s_all[te], g, thr_union)
        # specialist: CV + fit on this dataset only, thresholds on its own val
        cv_d = cv_choose_c(x_all[dtr], y_all[dtr], g_all[dtr], None)
        idf_d = idf_of(x_all[dtr])
        lr_d = fit(transform(x_all[dtr], idf_d), y_all[dtr], cv_d["best_C"])
        thr_d = thresholds(y_all[dva], decision(lr_d, transform(x_all[dva], idf_d)))
        block["tfidf_spec"] = evaluate(y, decision(lr_d, transform(x_all[te], idf_d)), g, thr_d)
        block["tfidf_spec"]["cv"] = cv_d  # type: ignore[index]
        # leave-one-dataset-out: train on the others, C from the union CV, union-style weights
        other = tr & ~d
        idf_o = idf_of(x_all[other])
        lr_o = fit(
            transform(x_all[other], idf_o),
            y_all[other],
            cv["best_C"],
            dataset_weights(df.dataset[other]),
        )
        s_o = decision(lr_o, transform(x_all, idf_o))
        thr_o = thresholds(y_all[va & ~d], s_o[va & ~d])
        block["tfidf_lodo"] = evaluate(y, s_o[te], g, thr_o)
        for lex in ("asks_frozen", "asks_product"):
            s_lex = df[lex].to_numpy(float)[te]
            block[lex] = evaluate(y, s_lex, g, {"tau_hi": 1.0, "tau_f1": 1.0})
        per[name] = block
        print(name, {k: v.get("auc", {}).get("value") for k, v in block.items()}, flush=True)
    report["per_dataset"] = per

    # ---- robustness: attacked fraud texts, union model with and without de-obfuscation
    te_idx = np.flatnonzero(is_te.to_numpy())
    fraud_te = [i for i in te_idx if y_all[i] == 1]
    legit_te = [i for i in te_idx if y_all[i] == 0]
    s_legit = s_all[legit_te]
    x_raw_tr = featurize(df.text[tr].tolist(), False, workers=2)
    idf_raw = idf_of(x_raw_tr)
    union_raw = fit(transform(x_raw_tr, idf_raw), y_all[tr], cv["best_C"], w_tr)
    s_raw_va = decision(union_raw, transform(featurize(df.text[va].tolist(), False), idf_raw))
    thr_raw = thresholds(y_all[va], s_raw_va)
    s_raw_legit = decision(
        union_raw, transform(featurize(df.text.iloc[legit_te].tolist(), False), idf_raw)
    )
    rob: dict[str, object] = {"n_fraud": len(fraud_te), "n_legit": len(legit_te)}
    for kind in ("clean", *ATTACKS):
        texts = [
            df.text.iloc[i]
            if kind == "clean"
            else attack(df.text.iloc[i], kind, f"{SEED}:{kind}:{i}")
            for i in fraud_te
        ]
        s_n = decision(union, transform(featurize(texts, True), idf))
        s_r = decision(union_raw, transform(featurize(texts, False), idf_raw))
        asks = [ask_count(t, True) for t in texts]
        row = {}
        for tag, s_f, s_l, t in (
            ("deobfuscated", s_n, s_legit, thr_union),
            ("raw", s_r, s_raw_legit, thr_raw),
        ):
            yy = np.r_[np.ones(len(s_f)), np.zeros(len(s_l))]
            ss = np.r_[s_f, s_l]
            row[tag] = {
                "tpr@tau_hi": wilson(int((s_f >= t["tau_hi"]).sum()), len(s_f)),
                "auc": round(auroc(yy.tolist(), ss.tolist()), 4),
            }
        row["asks_product_tpr"] = wilson(sum(1 for a in asks if a >= 1), len(asks))
        rob[kind] = row
        print(
            "attack",
            kind,
            row["deobfuscated"]["tpr@tau_hi"]["value"],
            row["raw"]["tpr@tau_hi"]["value"],
            flush=True,
        )
    report["robustness"] = rob

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "text_benchmark.json").write_text(json.dumps(report, indent=1) + "\n")
    export(union, idf, cv, thr_union, df)
    from research.text.report import render

    (RESULTS / "text_benchmark.md").write_text(render(report))
    print((RESULTS / "text_benchmark.md").read_text())


def export(lr, idf: np.ndarray, cv: dict, thr: dict[str, float], df: pd.DataFrame) -> None:
    """The union model -> config/text_model.npz + config/text_model.json (ships in Satya)."""
    coef = lr.coef_.ravel().astype(np.float32)
    ci, ii = np.flatnonzero(coef), np.flatnonzero(idf)
    path = ROOT / "config" / "text_model.npz"
    np.savez_compressed(
        path,
        coef_idx=ci.astype(np.int32),
        coef_val=coef[ci],
        idf_idx=ii.astype(np.int32),
        idf_val=idf[ii],
    )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    table_sha = hashlib.sha256((DATA / "table.parquet").read_bytes()).hexdigest()
    meta = {
        "version": f"textrisk-1.0+{digest[:10]}",
        "model": "hashed TF-IDF (word 1-2 + char_wb 2-5, 2^20 buckets, CRC-32) + logistic "
        "regression, de-obfuscation layer on",
        "intercept": float(lr.intercept_[0]),
        "normalise": True,
        "C": cv["best_C"],
        "thresholds": {k: round(v, 6) for k, v in thr.items()},
        "fpr_targets": {"tau_hi": 0.01, "tau_lo": 0.05},
        "trained_on": sorted(df[df.split == "train"].dataset.unique().tolist()),
        "train_rows": int((df.split == "train").sum()),
        "data_table_sha256": table_sha,
        "npz_sha256": digest,
        "licences": {s.name: s.licence for s in SOURCES},
    }
    (ROOT / "config" / "text_model.json").write_text(json.dumps(meta, indent=1) + "\n")


if __name__ == "__main__":
    main()
