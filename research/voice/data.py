"""Voice benchmark data: download (pinned revisions), seeded speaker-disjoint sampling, and the
first 5 s of every clip stored as int16 at 16 kHz OUTSIDE the repo ($SATYAPAN_VOICE_DATA,
default ../satyapan-data/audio). Protocol: docs/VOICE_DEEPFAKE.md.

    python -m research.voice.data          # -> clips/<split>.npz + results/voice_eval_manifest.json

Splits: train (ASVspoof 2019 LA train), val / test_itw (In-the-Wild, disjoint speakers),
test_asv (ASVspoof 2019 LA eval). No audio ever enters the repo; the manifest lists every clip
id, label, speaker and the sha256 of every downloaded file.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import random  # provenance: seeded-resampling-ok (speaker split, clip sampling)
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("SATYAPAN_VOICE_DATA", str(ROOT.parent / "satyapan-data" / "audio")))
RAW, CLIPS = DATA / "raw", DATA / "clips"
SEED = 20261024
SR = 16_000
WINDOW_S = 5.0  # = satyapan.voice.audio_io.WINDOW_SECONDS: the product scores 5 s windows
MIN_S = 1.0
SPLITS = ("train", "val", "test_itw", "test_asv")

HF = "https://huggingface.co/datasets"
ITW_REV = "f36fbe7e4e009e444a4985c66d76ab1d9439f901"
ASV_EVAL_REV = "e904f130e44a900cb7e444405d6b9edff30a5d19"
ASV_TRAIN_REV = "aea92dd83a9c56e070c0b1e9f02e7c0d96216a4c"
PROTOCOL_REV = "4ad1b061fa6dc502b30888ee467ed4115fdb44eb"
FILES = {
    **{
        f"itw_{i}.parquet": f"{HF}/SpeechAntiSpoofingBenchmarks/InTheWild/resolve/{ITW_REV}/"
        f"data/test-0000{i}-of-00008.parquet"
        for i in range(8)
    },
    **{
        f"asv_eval_{i}.parquet": f"{HF}/SpeechAntiSpoofingBenchmarks/ASVspoof2019_LA/resolve/"
        f"{ASV_EVAL_REV}/data/test-0000{i}-of-00009.parquet"
        for i in range(2)  # 2 of 9 shards: ~16k eval rows to sample 2,000 from
    },
    "asv19_train.parquet": f"{HF}/Bisher/ASVspoof_2019_LA/resolve/{ASV_TRAIN_REV}/"
    "data/train-00000-of-00001.parquet",
    "cm_eval_protocol.txt": f"{HF}/Nemez1z/asvspoof-2019-la/resolve/{PROTOCOL_REV}/"
    "ASVspoof2019_LA_cm_protocols/ASVspoof2019.LA.cm.eval.trl.txt",
}
N_TRAIN_PER_CLASS = 1500
VAL_SPEAKER_FRACTION = 0.30
N_VAL, N_TEST_ITW = 1500, 3000
N_ASV_BONAFIDE, N_ASV_PER_ATTACK = 700, 100


@dataclass
class Clip:
    id: str
    label: int  # 1 = spoof (synthetic / converted), 0 = bonafide
    speaker: str
    source: str
    attack: str = "-"
    audio: np.ndarray = field(default_factory=lambda: np.zeros(0, np.int16))


def fetch(name: str) -> Path:
    dest = RAW / name
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    subprocess.run(["curl", "-sSfL", "-o", str(tmp), FILES[name]], check=True)
    tmp.replace(dest)
    return dest


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def decode(raw: bytes) -> np.ndarray:
    """FLAC/WAV bytes -> first WINDOW_S seconds, 16 kHz mono int16 (empty if < MIN_S)."""
    import soundfile as sf

    x, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    if sr != SR:
        from scipy.signal import resample_poly

        g = np.gcd(int(sr), SR)
        x = resample_poly(x, SR // g, int(sr) // g).astype(np.float32)
    x = x[: int(WINDOW_S * SR)]
    if len(x) < MIN_S * SR:
        return np.zeros(0, np.int16)
    return np.round(np.clip(x, -1, 1) * 32767).astype(np.int16)


def _rows(path: Path, columns: list[str]):
    import pyarrow.parquet as pq

    return pq.ParquetFile(path).read(columns=columns).to_pandas()


def _audio(path: Path, rows: list[int]) -> dict[int, bytes]:
    import pyarrow.parquet as pq

    f = pq.ParquetFile(path)
    want, out, start = set(rows), {}, 0
    for g in range(f.metadata.num_row_groups):
        n = f.metadata.row_group(g).num_rows
        hit = [r for r in range(start, start + n) if r in want]
        if hit:
            col = f.read_row_group(g, columns=["audio"]).column(0)
            for r in hit:
                out[r] = col[r - start].as_py()["bytes"]
        start += n
    return out


def itw_clips() -> tuple[list[Clip], list[Clip]]:
    """In-the-Wild: 30% of speakers -> val, the rest -> test_itw (seeded), clips sampled."""
    meta = []
    for i in range(8):
        p = fetch(f"itw_{i}.parquet")
        df = _rows(p, ["label", "notes"])
        for r, (lab, notes) in enumerate(zip(df.label, df.notes, strict=True)):
            n = json.loads(notes)
            meta.append((f"itw_{i}.parquet", r, n["utterance_id"], int(lab), n["speaker"]))
    speakers = sorted({m[4] for m in meta})
    rng = random.Random(f"{SEED}:itw")
    rng.shuffle(speakers)
    val_spk = set(speakers[: round(VAL_SPEAKER_FRACTION * len(speakers))])
    val = [m for m in meta if m[4] in val_spk]
    test = [m for m in meta if m[4] not in val_spk]
    rng_val, rng_test = random.Random(f"{SEED}:itw:val"), random.Random(f"{SEED}:itw:test")
    picked = rng_val.sample(val, min(N_VAL, len(val))) + rng_test.sample(
        test, min(N_TEST_ITW, len(test))
    )
    by_file: dict[str, list[int]] = {}
    for m in picked:
        by_file.setdefault(m[0], []).append(m[1])
    audio = {f: _audio(RAW / f, rows) for f, rows in by_file.items()}
    out_val, out_test = [], []
    for m in picked:
        c = Clip(m[2], m[3], m[4], "in_the_wild", audio=decode(audio[m[0]][m[1]]))
        (out_val if m[4] in val_spk else out_test).append(c)
    return out_val, out_test


def asv_eval_clips() -> list[Clip]:
    proto = {}
    for line in fetch("cm_eval_protocol.txt").read_text().splitlines():
        spk, utt, _, attack, key = line.split()
        proto[utt] = (spk, attack, int(key == "spoof"))
    meta = []
    for i in range(2):
        df = _rows(fetch(f"asv_eval_{i}.parquet"), ["notes"])
        for r, notes in enumerate(df.notes):
            utt = json.loads(notes)["utterance_id"]
            spk, attack, lab = proto[utt]
            meta.append((f"asv_eval_{i}.parquet", r, utt, lab, spk, attack))
    rng = random.Random(f"{SEED}:asv_eval")
    picked = rng.sample([m for m in meta if m[3] == 0], N_ASV_BONAFIDE)
    for attack in sorted({m[5] for m in meta if m[3] == 1}):
        pool = [m for m in meta if m[5] == attack]
        picked += rng.sample(pool, min(N_ASV_PER_ATTACK, len(pool)))
    return _materialise(picked, "asvspoof2019_eval")


def asv_train_clips() -> list[Clip]:
    p = fetch("asv19_train.parquet")
    df = _rows(p, ["speaker_id", "audio_file_name", "system_id", "key"])
    meta = [
        ("asv19_train.parquet", r, utt, int(k), spk, sysid)
        for r, (spk, utt, sysid, k) in enumerate(
            zip(df.speaker_id, df.audio_file_name, df.system_id, df.key, strict=True)
        )
    ]
    rng = random.Random(f"{SEED}:asv_train")
    bona = [m for m in meta if m[3] == 0]
    picked = rng.sample(bona, min(N_TRAIN_PER_CLASS, len(bona)))
    attacks = sorted({m[5] for m in meta if m[3] == 1})
    per = N_TRAIN_PER_CLASS // len(attacks)
    for attack in attacks:
        picked += rng.sample([m for m in meta if m[5] == attack], per)
    return _materialise(picked, "asvspoof2019_train")


def _materialise(picked: list[tuple], source: str) -> list[Clip]:
    by_file: dict[str, list[int]] = {}
    for m in picked:
        by_file.setdefault(m[0], []).append(m[1])
    audio = {f: _audio(RAW / f, rows) for f, rows in by_file.items()}
    return [
        Clip(m[2], m[3], m[4], source, attack=m[5], audio=decode(audio[m[0]][m[1]])) for m in picked
    ]


def save(split: str, clips: list[Clip]) -> None:
    clips = [c for c in clips if len(c.audio)]
    CLIPS.mkdir(parents=True, exist_ok=True)
    lens = np.array([len(c.audio) for c in clips], np.int64)
    np.savez(
        CLIPS / f"{split}.npz",
        audio=np.concatenate([c.audio for c in clips]),
        offsets=np.r_[0, np.cumsum(lens)],
        ids=np.array([c.id for c in clips]),
        labels=np.array([c.label for c in clips], np.int8),
        speakers=np.array([c.speaker for c in clips]),
        attacks=np.array([c.attack for c in clips]),
        sources=np.array([c.source for c in clips]),
    )


@dataclass(frozen=True)
class Split:
    ids: np.ndarray
    labels: np.ndarray
    speakers: np.ndarray
    attacks: np.ndarray
    audio: list[np.ndarray]  # float32 in [-1, 1], <= 5 s each


def load(split: str) -> Split:
    z = np.load(CLIPS / f"{split}.npz")
    off, raw = z["offsets"], z["audio"]  # read each array once (NpzFile re-reads per access)
    audio = [raw[off[i] : off[i + 1]].astype(np.float32) / 32768.0 for i in range(len(off) - 1)]
    return Split(z["ids"], z["labels"].astype(int), z["speakers"], z["attacks"], audio)


def main() -> None:
    if not all((CLIPS / f"{s}.npz").exists() for s in SPLITS):  # deterministic; build once
        val, test_itw = itw_clips()
        parts = {
            "train": asv_train_clips(),
            "val": val,
            "test_itw": test_itw,
            "test_asv": asv_eval_clips(),
        }
        for split, clips in parts.items():
            save(split, clips)
    manifest = {
        "seed": SEED,
        "window_s": WINDOW_S,
        "files": {name: {"url": FILES[name], "sha256": sha256(RAW / name)} for name in FILES},
        "licences": {
            "in_the_wild": "CC-BY-SA-4.0 (Mueller et al. 2022); Apache-2.0 packaging",
            "asvspoof2019": "ODC-By (ASVspoof 2019 LA, Edinburgh DataShare)",
        },
        "splits": {},
    }
    for split in SPLITS:
        s = load(split)
        assert s.ids is not None
        manifest["splits"][split] = {  # type: ignore[index]
            "n": len(s.ids),
            "spoof": int(s.labels.sum()),
            "speakers": sorted(set(s.speakers.tolist())),
            "clips": [
                {"id": str(i), "label": int(lab), "speaker": str(spk), "attack": str(a)}
                for i, lab, spk, a in zip(s.ids, s.labels, s.speakers, s.attacks, strict=True)
            ],
        }
        print(split, manifest["splits"][split]["n"], manifest["splits"][split]["spoof"])  # type: ignore[index]
    val_spk = set(manifest["splits"]["val"]["speakers"])  # type: ignore[index]
    test_spk = set(manifest["splits"]["test_itw"]["speakers"])  # type: ignore[index]
    assert not val_spk & test_spk, "val and test_itw share a speaker"
    (ROOT / "results" / "voice_eval_manifest.json").write_text(
        json.dumps(manifest, indent=0) + "\n"
    )


if __name__ == "__main__":
    main()
