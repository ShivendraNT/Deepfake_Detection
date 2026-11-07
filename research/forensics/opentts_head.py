"""Train and test a second voice head for open-source neural TTS (pre-registered rule).

    uv run python -m research.forensics.opentts_head          # features (cached), fit, test
    uv run python -m research.forensics.opentts_head --export # + config/voice_opentts_head.json

Why: research/forensics/voice_tts_probe.py showed that every off-the-shelf voice-deepfake
model we had (best: AST-ASVspoof5, AUC 0.84) misses Piper / VITS speech, the kind of voice
anyone can clone offline today. This head re-uses the shipped XLS-R trunk (no new model at
run time): its mean-pooled hidden states feed a standardised logistic regression.

Data (all public; nothing committed):
  real  train: LibriTTS-R dev-clean (CC BY 4.0), FLEURS Hindi dev (CC BY 4.0), LJSpeech
        test : LibriTTS-R test-clean and FLEURS Hindi test (speakers never seen in training)
  TTS   train: Piper voices amy, ryan, joe, kristin (en_US), alan, alba, cori (en_GB), 60
               LibriTTS-R and 30 VCTK speakers of Piper's multi-speaker models, pratham (hi_IN)
        test : HELD-OUT voices ljspeech, lessac, hfc_female (en_US), jenny_dioco (en_GB),
               l2arctic and arctic speakers, rohan and priyamvada (hi_IN)
Every clip is scored both clean and through 16 kHz Opus (WhatsApp-like), at random.

Rule (fixed before running): C is chosen by 5-fold grouped CV on training voices/speakers;
tau_lo / tau_hi are the 95th / 99th percentiles of held-in validation real clips. The head
ships only if, on the held-out test set, AUC >= 0.90 and at tau_hi >= 50% of TTS clips are
flagged with <= 2% of real clips flagged (English and Hindi reported separately).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import tarfile
import wave
from pathlib import Path

import numpy as np

from research.forensics.aigen_select import auc

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT.parent / "satyapan-data" / "opentts"
OUT_RES = ROOT / "results" / "voice_opentts_head.json"
OUT_CFG = ROOT / "config" / "voice_opentts_head.json"
SR = 16000
TRAIN_VOICES = {
    "en_US-amy-medium": "en/en_US/amy/medium/", "en_US-ryan-high": "en/en_US/ryan/high/",
    "en_US-joe-medium": "en/en_US/joe/medium/", "en_US-kristin-medium": "en/en_US/kristin/medium/",
    "en_GB-alan-medium": "en/en_GB/alan/medium/", "en_GB-alba-medium": "en/en_GB/alba/medium/",
    "en_GB-cori-high": "en/en_GB/cori/high/", "hi_IN-pratham-medium": "hi/hi_IN/pratham/medium/",
    "en_US-libritts_r-medium": "en/en_US/libritts_r/medium/", "en_GB-vctk-medium": "en/en_GB/vctk/medium/",
}  # fmt: skip
TEST_VOICES = {
    "en_US-ljspeech-high": "en/en_US/ljspeech/high/", "en_US-lessac-high": "en/en_US/lessac/high/",
    "en_US-hfc_female-medium": "en/en_US/hfc_female/medium/",
    "en_GB-jenny_dioco-medium": "en/en_GB/jenny_dioco/medium/",
    "en_US-l2arctic-medium": "en/en_US/l2arctic/medium/", "en_US-arctic-medium": "en/en_US/arctic/medium/",
    "hi_IN-rohan-medium": "hi/hi_IN/rohan/medium/", "hi_IN-priyamvada-medium": "hi/hi_IN/priyamvada/medium/",
}  # fmt: skip
MULTI = {"en_US-libritts_r-medium": 60, "en_GB-vctk-medium": 30, "en_US-l2arctic-medium": 12,
         "en_US-arctic-medium": 12}  # fmt: skip


def opus_roundtrip(x: np.ndarray) -> np.ndarray:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    enc = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-c:a", "libopus", "-b:a",
                          "24k", "-application", "voip", "-f", "ogg", "pipe:1"],
                         input=buf.getvalue(), capture_output=True, check=True).stdout  # fmt: skip
    dec = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "pipe:1"], input=enc, capture_output=True, check=True).stdout  # fmt: skip
    return np.frombuffer(dec, np.float32).copy()


def to16k(x: np.ndarray, sr: int) -> np.ndarray:
    from scipy.signal import resample_poly

    if sr == SR:
        return x.astype(np.float32)
    g = np.gcd(sr, SR)
    return resample_poly(x, SR // g, sr // g).astype(np.float32)


def libritts(split: str, n: int, seed: int) -> tuple[list[tuple[np.ndarray, str]], list[str]]:
    import pyarrow.parquet as pq
    import soundfile as sf
    from huggingface_hub import hf_hub_download

    p = hf_hub_download("mythicinfinity/libritts_r", f"data/{split}/{split}-00000-of-0000{4 if split == 'dev.clean' else 3}.parquet",
                        repo_type="dataset")  # fmt: skip
    tab = pq.read_table(p, columns=["audio", "speaker_id", "text_normalized"])
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(tab))
    out, texts = [], []
    for i in idx:
        a = tab.column("audio")[int(i)].as_py()
        x, sr = sf.read(io.BytesIO(a["bytes"]), dtype="float32")
        if x.ndim > 1:
            x = x.mean(axis=1)
        if len(x) < sr * 2.5:
            continue
        out.append((to16k(x, sr), f"libritts:{tab.column('speaker_id')[int(i)].as_py()}"))
        texts.append(str(tab.column("text_normalized")[int(i)].as_py()))
        if len(out) >= n:
            break
    return out, texts


def fleurs_hi(split: str, n: int, seed: int) -> tuple[list[tuple[np.ndarray, str]], list[str]]:
    import soundfile as sf
    from huggingface_hub import hf_hub_download

    tsv = hf_hub_download("google/fleurs", f"data/hi_in/{split}.tsv", repo_type="dataset")
    tar = hf_hub_download("google/fleurs", f"data/hi_in/audio/{split}.tar.gz", repo_type="dataset")
    rows = {}
    with open(tsv, encoding="utf-8") as fh:
        for r in csv.reader(fh, delimiter="\t"):
            if len(r) >= 3:
                rows[r[1]] = (r[2], r[-2] if len(r) > 5 else "")
    out, texts = [], []
    rng = np.random.default_rng(seed)
    keep_every = 3  # spread the sample over the archive (it is read sequentially: gzip cannot seek)
    offset = int(rng.integers(keep_every))
    with tarfile.open(tar, "r|gz") as tf:
        k = 0
        for mem in tf:
            if not mem.name.endswith(".wav"):
                continue
            k += 1
            if (k + offset) % keep_every:
                continue
            fh = tf.extractfile(mem)
            if fh is None:
                continue
            x, sr = sf.read(io.BytesIO(fh.read()), dtype="float32")
            if x.ndim > 1:
                x = x.mean(axis=1)
            if len(x) < sr * 2.5:
                continue
            name = mem.name.rsplit("/", 1)[-1]
            spk = rows.get(name, ("", ""))[1] or name
            out.append((to16k(x, sr), f"fleurs:{spk}"))
            texts.append(rows.get(name, ("", ""))[0])
            if len(out) >= n:
                break
    return out, texts


def ljspeech(n: int) -> list[tuple[np.ndarray, str]]:
    from huggingface_hub import hf_hub_download

    out = []
    for k in range(1, n + 1):
        p = hf_hub_download("flexthink/ljspeech", f"wavs/LJ003-{k:04d}.wav", repo_type="dataset")
        with wave.open(p) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
            out.append((to16k(x, w.getframerate()), "ljspeech:real"))
    return out


def piper_clips(voices: dict[str, str], en_texts: list[str], hi_texts: list[str], per_voice: int,
                seed: int) -> list[tuple[np.ndarray, str]]:  # fmt: skip
    from huggingface_hub import hf_hub_download
    from piper import PiperVoice, SynthesisConfig

    rng = np.random.default_rng(seed)
    out = []
    for name, sub in voices.items():
        onnx = hf_hub_download("rhasspy/piper-voices", sub + name + ".onnx")
        hf_hub_download("rhasspy/piper-voices", sub + name + ".onnx.json")
        v = PiperVoice.load(onnx)
        texts = hi_texts if name.startswith("hi") else en_texts
        n_spk = MULTI.get(name, 1)
        n_total = per_voice * (4 if n_spk > 1 else 1)
        for _j in range(n_total):
            t = texts[int(rng.integers(len(texts)))]
            sid = int(rng.integers(v.config.num_speakers)) if v.config.num_speakers > 1 else None
            cfg = SynthesisConfig(speaker_id=sid, length_scale=float(rng.uniform(0.9, 1.15)),
                                  noise_scale=float(rng.uniform(0.5, 0.8)))  # fmt: skip
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                v.synthesize_wav(t, w, syn_config=cfg)
            buf.seek(0)
            with wave.open(buf) as w:
                x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
                sr = w.getframerate()
            if len(x) > sr * 1.5:
                out.append((to16k(x, sr), f"{name}:{sid if sid is not None else 0}"))
        print(f"  {name}: {n_total} clips", flush=True)
    return out


def features(
    clips: list[tuple[np.ndarray, str]], seed: int
) -> tuple[np.ndarray, list[str], list[int]]:
    from satyapan.voice.detector import load_default_detector

    det = load_default_detector("probe")
    sess = det.model_session
    inp = sess.get_inputs()[0].name
    rng = np.random.default_rng(seed)
    feats, groups, opus = [], [], []
    for x, g in clips:
        use_opus = int(rng.random() < 0.5)
        y = opus_roundtrip(x) if use_opus else x
        y = y[: SR * 5]
        hs = sess.run(None, {inp: y[None, :].astype(np.float32)})[0]
        feats.append(hs.mean(axis=1)[0])
        groups.append(g)
        opus.append(use_opus)
    return np.array(feats, np.float32), groups, opus


def cached(name: str, make) -> dict:  # type: ignore[no-untyped-def]
    DATA.mkdir(parents=True, exist_ok=True)
    p = DATA / f"{name}.npz"
    if p.exists():
        d = np.load(p, allow_pickle=True)
        return {k: d[k] for k in d.files}
    X, g, o = make()
    np.savez(p, X=X, groups=np.array(g), opus=np.array(o))
    return {"X": X, "groups": np.array(g), "opus": np.array(o)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", action="store_true")
    args = ap.parse_args()
    print("real train / test", flush=True)
    lt_tr, en_tr_texts = libritts("dev.clean", 360, 1)
    fh_tr, hi_tr_texts = fleurs_hi("dev", 200, 2)
    real_tr = cached("real_train", lambda: features(lt_tr + fh_tr + ljspeech(40), 11))
    lt_te, en_te_texts = libritts("test.clean", 300, 3)
    fh_te, hi_te_texts = fleurs_hi("test", 200, 4)
    real_te = cached("real_test", lambda: features(lt_te + fh_te, 12))
    print("TTS train / test", flush=True)
    fake_tr = cached(
        "tts_train",
        lambda: features(piper_clips(TRAIN_VOICES, en_tr_texts, hi_tr_texts, 24, 5), 13),
    )
    fake_te = cached(
        "tts_test", lambda: features(piper_clips(TEST_VOICES, en_te_texts, hi_te_texts, 20, 6), 14)
    )
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold
    from sklearn.preprocessing import StandardScaler

    X = np.concatenate([real_tr["X"], fake_tr["X"]])
    y = np.concatenate([np.zeros(len(real_tr["X"])), np.ones(len(fake_tr["X"]))])
    g = np.concatenate([real_tr["groups"], fake_tr["groups"]])
    best_c, best_auc = 1.0, -1.0
    for c in (0.001, 0.003, 0.01, 0.03, 0.1, 0.3):
        aucs = []
        for tr, va in GroupKFold(n_splits=5).split(X, y, g):
            sc = StandardScaler().fit(X[tr])
            m = LogisticRegression(C=c, max_iter=3000).fit(sc.transform(X[tr]), y[tr])
            s = m.decision_function(sc.transform(X[va]))
            if len(set(y[va])) == 2:
                aucs.append(auc(s[y[va] == 1], s[y[va] == 0]))
        if np.mean(aucs) > best_auc:
            best_c, best_auc = c, float(np.mean(aucs))
        print(f"  C={c}: CV AUC {np.mean(aucs):.3f}", flush=True)
    sc = StandardScaler().fit(X)
    m = LogisticRegression(C=best_c, max_iter=3000).fit(sc.transform(X), y)
    # thresholds from out-of-fold real scores (validation reals, never the test set)
    oof = np.zeros(len(X))
    for tr, va in GroupKFold(n_splits=5).split(X, y, g):
        s2 = StandardScaler().fit(X[tr])
        m2 = LogisticRegression(C=best_c, max_iter=3000).fit(s2.transform(X[tr]), y[tr])
        oof[va] = m2.decision_function(s2.transform(X[va]))
    tau_lo, tau_hi = float(np.quantile(oof[y == 0], 0.95)), float(np.quantile(oof[y == 0], 0.99))
    s_real = m.decision_function(sc.transform(real_te["X"]))
    s_fake = m.decision_function(sc.transform(fake_te["X"]))
    te_auc = auc(s_fake, s_real)
    res = {"rule": __doc__.split("Rule (fixed before running):")[1].strip(), "C": best_c,
           "cv_auc": best_auc, "tau_lo": tau_lo, "tau_hi": tau_hi, "test_auc": te_auc,
           "test_tts_flagged_tau_hi": float((s_fake >= tau_hi).mean()),
           "test_tts_flagged_tau_lo": float((s_fake >= tau_lo).mean()),
           "test_real_flagged_tau_hi": float((s_real >= tau_hi).mean()),
           "test_real_flagged_tau_lo": float((s_real >= tau_lo).mean()),
           "n": {"real_train": len(real_tr["X"]), "tts_train": len(fake_tr["X"]),
                 "real_test": len(s_real), "tts_test": len(s_fake)}}  # fmt: skip
    gr = real_te["groups"]
    for lang, pref in (("english", "libritts"), ("hindi", "fleurs")):
        mask = np.array([str(x).startswith(pref) for x in gr])
        res[f"test_real_flagged_tau_hi_{lang}"] = float((s_real[mask] >= tau_hi).mean())
        res[f"test_real_flagged_tau_lo_{lang}"] = float((s_real[mask] >= tau_lo).mean())
    per = {}
    for s, grp in zip(s_fake, fake_te["groups"], strict=True):
        per.setdefault(str(grp).split(":")[0], []).append(float(s >= tau_hi))
    res["test_per_voice_flagged_tau_hi"] = {k: float(np.mean(v)) for k, v in per.items()}
    for cond in (0, 1):
        mf, mr = fake_te["opus"] == cond, real_te["opus"] == cond
        res[f"test_auc_{'opus' if cond else 'clean'}"] = auc(s_fake[mf], s_real[mr])
    res["ships"] = bool(te_auc >= 0.90 and res["test_tts_flagged_tau_hi"] >= 0.5
                        and res["test_real_flagged_tau_hi"] <= 0.02)  # fmt: skip
    print(json.dumps(res, indent=1), flush=True)
    OUT_RES.write_text(json.dumps(res, indent=1))
    if args.export:
        cfg = {"name": "Satyapan open-TTS head (XLS-R trunk + logistic regression)",
               "trunk": "gustking_xlsr model.onnx mean-pooled hidden states",
               "mean": sc.mean_.tolist(), "scale": sc.scale_.tolist(),
               "coef": m.coef_[0].tolist(), "intercept": float(m.intercept_[0]),
               "tau_lo": tau_lo, "tau_hi": tau_hi, "ships": res["ships"],
               "metrics": {k: res[k] for k in ("test_auc", "test_tts_flagged_tau_hi",
                                               "test_real_flagged_tau_hi", "test_real_flagged_tau_hi_hindi",
                                               "test_real_flagged_tau_hi_english", "test_auc_opus")},
               "held_out_voices": list(TEST_VOICES)}  # fmt: skip
        OUT_CFG.write_text(json.dumps(cfg))
        print("wrote", OUT_CFG)


if __name__ == "__main__":
    main()
