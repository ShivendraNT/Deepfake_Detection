"""Export the selected voice model in the two-file format every Satya scorer already reads.

    python -m research.voice.export            # the model results/voice_selection.json chose
    python -m research.voice.export --install  # + copy to extension/models/ (= `make voice`)
    python -m research.voice.export --model satya_xlsr_l7     # a specific candidate

model.onnx        input "input"  [1, n] raw 16 kHz mono float32 (normalised inside the graph)
                  output "output" [1, T, 1024] hidden states
logreg_prob.onnx  input "X" [1, 1024] (mean over T) -> output "probabilities" [1, 2],
                  column 1 = P(synthetic) = sigmoid(standardise(X) . w + b)

This is the format of the Pascu et al. browser plug-in (extension/lib/onnx_scorer.js, the
desktop capture window, satyapan.voice.detector.OnnxVoiceDetector), so any selected model
ships with no scorer code change:

* ours (`satya_xlsr_l7`): XLS-R layers 1-7 + our logistic regression (research/voice/bench.py);
* a Hugging Face Wav2Vec2ForSequenceClassification (e.g. `gustking_xlsr`): all layers; its
  projector, mean pool and classifier are linear after the pool, so logit(fake) - logit(real)
  = w . mean(states) + b exactly, which is the same head with mean 0 and scale 1.

check() compares both graphs with the PyTorch model on 8 clips (deterministic test tones when
the benchmark data is absent, e.g. on a judge's laptop).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from research.voice.data import DATA, ROOT

OUT = DATA / "models"
MODEL, HEAD = OUT / "model.onnx", OUT / "logreg_prob.onnx"  # ours (also feeds bench features)
HEAD_CONFIG = ROOT / "config" / "voice_head.json"
SELECTION = ROOT / "results" / "voice_selection.json"
OURS = "satya_xlsr_l7"


def paths(name: str) -> tuple[Path, Path]:
    d = OUT if name == OURS else OUT / name
    return d / "model.onnx", d / "logreg_prob.onnx"


def selected() -> str:
    return str(json.loads(SELECTION.read_text())["decision"]) if SELECTION.exists() else OURS


def _normalise(wav):  # Wav2Vec2FeatureExtractor(do_normalize=True), inside the graph
    import torch

    return (wav - wav.mean(dim=1, keepdim=True)) / torch.sqrt(
        wav.var(dim=1, keepdim=True, unbiased=False) + 1e-7
    )


def _export(module, dest: Path) -> None:
    import torch

    dest.parent.mkdir(parents=True, exist_ok=True)
    example = torch.zeros(1, 32000)
    example[0, ::7] = 0.1  # any non-constant input traces the graph
    torch.onnx.export(
        module.eval(), (example,), str(dest), input_names=["input"],
        output_names=["output"], dynamic_axes={"input": {1: "n"}, "output": {1: "t"}},
        opset_version=17, dynamo=False,
    )  # fmt: skip


def _hf(name: str):
    from transformers import AutoModelForAudioClassification

    from research.voice.models import BY_NAME

    c = BY_NAME[name]
    return AutoModelForAudioClassification.from_pretrained(c.repo, revision=c.revision).eval()


def export_trunk(name: str) -> None:
    import torch

    if name == OURS:
        from research.voice.models import xlsr_trunk

        trunk = xlsr_trunk()

        class States(torch.nn.Module):  # the trunk without the mean pool
            def __init__(self) -> None:
                super().__init__()
                self.t = trunk

            def forward(self, wav: torch.Tensor) -> torch.Tensor:
                t = self.t
                h = t.feature_extractor(_normalise(wav)).transpose(1, 2)
                h, _ = t.feature_projection(h)
                h = h + t.pos_conv_embed(h)
                for layer in t.layers:
                    out = layer(h)
                    h = out[0] if isinstance(out, tuple) else out
                return h

        _export(States(), paths(name)[0])
        return
    net = _hf(name)

    class HfStates(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.w2v = net.wav2vec2

        def forward(self, wav: torch.Tensor) -> torch.Tensor:
            return self.w2v(_normalise(wav)).last_hidden_state

    _export(HfStates(), paths(name)[0])


def head_of(name: str) -> dict:
    """{mean, scale, coef, intercept}: the benchmark's fitted head for ours (or the committed
    copy), the folded projector + classifier for a Hugging Face classifier."""
    if name == OURS:
        f = DATA / "ours_head.json"
        return dict(json.loads((f if f.exists() else HEAD_CONFIG).read_text()))
    net = _hf(name)
    labels = {v.lower(): int(k) for k, v in net.config.id2label.items()}
    fake = next(labels[k] for k in ("fake", "spoof") if k in labels)
    real = next(labels[k] for k in ("real", "bonafide") if k in labels)
    wc = net.classifier.weight.detach().numpy().astype(np.float64)
    bc = net.classifier.bias.detach().numpy().astype(np.float64)
    wp = net.projector.weight.detach().numpy().astype(np.float64)
    bp = net.projector.bias.detach().numpy().astype(np.float64)
    d = wc[fake] - wc[real]
    n = wp.shape[1]
    return {"mean": [0.0] * n, "scale": [1.0] * n, "coef": (d @ wp).tolist(),
            "intercept": float(d @ bp + bc[fake] - bc[real])}  # fmt: skip


def export_head(name: str) -> None:
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    head = head_of(name)
    mean = np.array(head["mean"], np.float32)
    scale = np.array(head["scale"], np.float32)
    w = (np.array(head["coef"], np.float32) / scale).reshape(-1, 1)  # fold the standardiser in
    b = np.array([head["intercept"] - float((mean / scale) @ np.array(head["coef"]))], np.float32)
    inits = [numpy_helper.from_array(w, "w"), numpy_helper.from_array(b, "b"),
             numpy_helper.from_array(np.array([1.0], np.float32), "one")]  # fmt: skip
    nodes = [
        helper.make_node("MatMul", ["X", "w"], ["z0"]),
        helper.make_node("Add", ["z0", "b"], ["z"]),
        helper.make_node("Sigmoid", ["z"], ["p"]),
        helper.make_node("Sub", ["one", "p"], ["q"]),
        helper.make_node("Concat", ["q", "p"], ["probabilities"], axis=1),
    ]
    graph = helper.make_graph(
        nodes, "satya_voice_head",
        [helper.make_tensor_value_info("X", TensorProto.FLOAT, [1, len(mean)])],
        [helper.make_tensor_value_info("probabilities", TensorProto.FLOAT, [1, 2])], inits,
    )  # fmt: skip
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8  # readable by onnxruntime-web as well
    onnx.checker.check_model(model)
    onnx.save(model, str(paths(name)[1]))


def tones() -> list[np.ndarray]:
    """Deterministic 3 s test signals (no benchmark data needed on a judge's laptop)."""
    t = np.arange(48000, dtype=np.float32) / 16000
    return [(0.1 * np.sin(2 * np.pi * f * t * (1 + 0.1 * t))).astype(np.float32)
            for f in (110, 180, 220, 330, 440, 660, 880, 1200)]  # fmt: skip


def reference(name: str):
    """clip -> the benchmark's own logit for this model, computed in PyTorch."""
    import torch

    if name != OURS:
        from research.voice.models import hf_classifier

        return hf_classifier(name)
    from research.voice.models import xlsr_trunk

    head, trunk = head_of(name), xlsr_trunk()
    mean, scale, coef = (np.array(head[k]) for k in ("mean", "scale", "coef"))

    def logit(x: np.ndarray) -> float:
        with torch.inference_mode():
            e = trunk(torch.from_numpy(x[None, :].astype(np.float32)))[0].numpy()
        return float(((e - mean) / scale) @ coef + head["intercept"])

    return logit


def check(name: str) -> None:
    import onnxruntime as ort

    from research.voice.data import load

    model, head = paths(name)
    m = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    h = ort.InferenceSession(str(head), providers=["CPUExecutionProvider"])
    ref_fn = reference(name)
    clips = load("val").audio[:8] if (DATA / "clips" / "val.npz").exists() else tones()
    ref, got = [], []
    for x in clips:
        ref.append(ref_fn(x))
        states = m.run(None, {"input": x[None, :]})[0]
        p = float(h.run(None, {"X": states.mean(axis=1).astype(np.float32)})[0][0, 1])
        p = min(max(p, 1e-7), 1 - 1e-7)
        got.append(float(np.log(p / (1 - p))))
    diff = float(np.abs(np.array(got) - np.array(ref)).max())
    print(f"{name}: {model.name} {model.stat().st_size / 1e6:.0f} MB; "
          f"max |logit diff| vs PyTorch {diff:.2e}")  # fmt: skip
    if diff > 1e-2:
        raise SystemExit("ONNX export does not match PyTorch")


def install(name: str) -> None:
    """Copy both files to where every scorer reads them (extension/models/) and the head
    weights to config/voice_head.json (1,024 numbers per vector; no audio)."""
    import shutil

    from research.voice.models import BY_NAME
    from satyapan.voice.detector import MODEL_DIR

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for f in paths(name):
        dest = MODEL_DIR / f.name
        dest.unlink(missing_ok=True)
        try:
            os.link(f, dest)  # same disk: no second 1.3 GB copy
        except OSError:
            shutil.copyfile(f, dest)
    c = BY_NAME[name]
    head = head_of(name)
    out = {k: head[k] for k in ("mean", "scale", "coef", "intercept")}
    out.update({"model": name, "repo": c.repo, "revision": c.revision, "licence": c.licence,
                "trained_on": c.trained_on})  # fmt: skip
    HEAD_CONFIG.write_text(json.dumps(out) + "\n")
    print(f"installed {name} in {MODEL_DIR}; head -> {HEAD_CONFIG}")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None, help="default: the decision in voice_selection")
    ap.add_argument("--install", action="store_true", help="also copy into extension/models")
    a = ap.parse_args()
    name = a.model or selected()
    if not paths(name)[0].exists():
        export_trunk(name)
    export_head(name)
    check(name)
    if a.install:
        install(name)


if __name__ == "__main__":
    main()
