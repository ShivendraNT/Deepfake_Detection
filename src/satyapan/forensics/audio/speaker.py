"""Speaker embeddings for voice comparison (WeSpeaker ResNet34-LM, VoxCeleb, CC-BY-4.0, ONNX).

Front end: Kaldi-compatible 80-bin log-mel filterbank (25 ms / 10 ms, Hamming window,
pre-emphasis 0.97, DC removal, 512-point FFT, mel 20 Hz - Nyquist) on 16-bit-scaled audio,
followed by per-utterance mean normalisation, as in WeSpeaker's recipe. Tests compare it with
torchaudio.compliance.kaldi.fbank when torchaudio is installed.

Score: cosine similarity of the embeddings. WeSpeaker reports EER 0.72 % on VoxCeleb1-O for
this model; the lab's decision thresholds are in config/speaker_thresholds.json.
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

SR = 16000


def _mel(f: np.ndarray) -> np.ndarray:
    return 1127.0 * np.log(1.0 + f / 700.0)


def mel_banks(num_bins: int = 80, n_fft: int = 512, sr: int = SR, low: float = 20.0,
              high: float = 0.0) -> np.ndarray:  # fmt: skip
    """Kaldi's triangular mel filters (in the mel domain), shape [num_bins, n_fft // 2]."""
    nyq = sr / 2.0
    high = high if high > 0 else nyq + high
    mlo, mhi = _mel(np.array(low)), _mel(np.array(high))
    delta = (mhi - mlo) / (num_bins + 1)
    fft_mel = _mel(np.arange(n_fft // 2) * sr / n_fft)
    banks = np.zeros((num_bins, n_fft // 2), dtype=np.float64)
    for b in range(num_bins):
        left, center, right = mlo + b * delta, mlo + (b + 1) * delta, mlo + (b + 2) * delta
        up = (fft_mel - left) / (center - left)
        down = (right - fft_mel) / (right - center)
        banks[b] = np.maximum(0.0, np.minimum(up, down))
    return banks


_BANKS = mel_banks()


def fbank(x16k: np.ndarray) -> np.ndarray:
    """[T, 80] log-mel features, Kaldi defaults as used by WeSpeaker (dither 0)."""
    wav = x16k.astype(np.float64) * 32768.0
    fl, hop, n_fft = 400, 160, 512
    if len(wav) < fl:
        raise ValueError("audio shorter than one 25 ms frame")
    n = 1 + (len(wav) - fl) // hop
    idx = np.arange(fl)[None, :] + hop * np.arange(n)[:, None]
    fr = wav[idx]
    fr = fr - fr.mean(axis=1, keepdims=True)
    pre = np.concatenate([fr[:, :1] * (1 - 0.97), fr[:, 1:] - 0.97 * fr[:, :-1]], axis=1)
    win = 0.54 - 0.46 * np.cos(2 * np.pi * np.arange(fl) / (fl - 1))
    spec = np.abs(np.fft.rfft(pre * win, n=n_fft, axis=1)) ** 2
    mel = spec[:, : n_fft // 2] @ _BANKS.T
    feats = np.log(np.maximum(mel, np.finfo(np.float32).eps))
    return (feats - feats.mean(axis=0, keepdims=True)).astype(np.float32)


class SpeakerEmbedder:
    def __init__(self, path: Path) -> None:
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        self.session = ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])
        self._lock = threading.Lock()

    def embed(self, x16k: np.ndarray, max_s: float = 60.0) -> np.ndarray:
        x = x16k[: int(max_s * SR)]
        feats = fbank(x)[None]
        with self._lock:
            emb = self.session.run(None, {"feats": feats})[0][0]
        return emb / (np.linalg.norm(emb) + 1e-9)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
