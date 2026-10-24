"""Voice candidates (docs/VOICE_DEEPFAKE.md §3): our XLS-R layer-7 + LR model and four
off-the-shelf Hugging Face detectors, each a function from one 16 kHz float32 clip to one
fake-logit. Revisions are pinned; nothing here is fitted except our LR head (bench.py).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

XLSR_REPO = "facebook/wav2vec2-xls-r-300m"
XLSR_REV = "1a640f32ac3e39899438a2931f9924c02f080a54"
XLSR_LAYERS = 7  # Pascu et al.: mid layers of XLS-R generalise best out of domain


@dataclass(frozen=True)
class Candidate:
    name: str
    repo: str
    revision: str
    licence: str
    params_m: float
    trained_on: str
    eligible: bool  # licence + documented training data without In-the-Wild


CANDIDATES = (
    Candidate("satya_xlsr_l7", XLSR_REPO, XLSR_REV, "Apache-2.0 (backbone) + our LR head", 96.0,
              "ASVspoof 2019 LA train, 3,000 clips (ours)", True),
    Candidate("gustking_xlsr", "Gustking/wav2vec2-large-xlsr-deepfake-audio-classification",
              "f7050b586236dc910d1157f430def2d0647b02b4", "Apache-2.0", 315.0,
              "ASVspoof 2019 (per its card)", True),
    Candidate("garystafford_xlsr", "garystafford/wav2vec2-deepfake-voice-detector",
              "c66306024a7ede0be291e9c4558b37634782dc4e", "Apache-2.0", 315.0,
              "garystafford/deepfake-audio-detection (CC-BY-4.0; TTS / cloning services)", True),
    Candidate("melody_w2v2", "MelodyMachine/Deepfake-audio-detection-V2",
              "de3cde5a29c449bb5268814e421b46bf6ebdcd72", "Apache-2.0", 94.0,
              "undocumented 'audiofolder'", False),
    Candidate("ast_asvspoof5", "MattyB95/AST-ASVspoof5-Synthetic-Voice-Detection",
              "f8187e7a7e8885df82c855ae833d4cf9d6f0d816", "BSD-3-Clause", 86.0,
              "ASVspoof5 (per its card)", True),
)  # fmt: skip
BY_NAME = {c.name: c for c in CANDIDATES}


def xlsr_trunk():
    """XLS-R-300m cut after XLSR_LAYERS transformer layers: waveform -> (T, 1024) states."""
    import torch
    from transformers import Wav2Vec2Model

    full = Wav2Vec2Model.from_pretrained(XLSR_REPO, revision=XLSR_REV).eval()

    class Trunk(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.feature_extractor = full.feature_extractor
            self.feature_projection = full.feature_projection
            self.pos_conv_embed = full.encoder.pos_conv_embed
            self.layers = torch.nn.ModuleList(full.encoder.layers[:XLSR_LAYERS])

        def forward(self, wav: torch.Tensor) -> torch.Tensor:
            """wav: (1, n) float32 at 16 kHz -> (1, 1024) mean of layer-7 states."""
            wav = (wav - wav.mean(dim=1, keepdim=True)) / torch.sqrt(
                wav.var(dim=1, keepdim=True, unbiased=False) + 1e-7
            )  # Wav2Vec2FeatureExtractor(do_normalize=True)
            h = self.feature_extractor(wav).transpose(1, 2)
            h, _ = self.feature_projection(h)
            h = h + self.pos_conv_embed(h)
            for layer in self.layers:
                out = layer(h)
                h = out[0] if isinstance(out, tuple) else out  # transformers 4 vs 5
            return h.mean(dim=1)

    return Trunk().eval()


def xlsr_features() -> Callable[[np.ndarray], np.ndarray]:
    """Clip -> 1024-d mean layer-7 embedding. Uses the exported ONNX trunk (the file the
    product ships) when it exists: same numbers to 1e-4, about 30 % faster on CPU."""
    from research.voice.export import MODEL

    if MODEL.exists():
        import onnxruntime as ort

        so = ort.SessionOptions()
        so.intra_op_num_threads, so.inter_op_num_threads = 2, 1
        sess = ort.InferenceSession(str(MODEL), so, providers=["CPUExecutionProvider"])

        def embed_onnx(x: np.ndarray) -> np.ndarray:
            return sess.run(None, {"input": x[None, :].astype(np.float32)})[0][0].mean(axis=0)

        return embed_onnx
    import torch

    trunk = xlsr_trunk()

    def embed(x: np.ndarray) -> np.ndarray:
        with torch.inference_mode():
            return trunk(torch.from_numpy(x[None, :].astype(np.float32)))[0].numpy()

    return embed


def hf_classifier(name: str) -> Callable[[np.ndarray], float]:
    """An off-the-shelf audio classifier -> logit(fake) - logit(real)."""
    import torch
    from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

    c = BY_NAME[name]
    fx = AutoFeatureExtractor.from_pretrained(c.repo, revision=c.revision)
    net = AutoModelForAudioClassification.from_pretrained(c.repo, revision=c.revision).eval()
    labels = {v.lower(): int(k) for k, v in net.config.id2label.items()}
    fake = next(labels[k] for k in ("fake", "spoof") if k in labels)
    real = next(labels[k] for k in ("real", "bonafide") if k in labels)

    def score(x: np.ndarray) -> float:
        enc = fx(x, sampling_rate=16000, return_tensors="pt")
        with torch.inference_mode():
            lg = net(**enc).logits[0]
        return float(lg[fake] - lg[real])

    return score
