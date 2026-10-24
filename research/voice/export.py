"""Export our voice model in the two-file format every Satya scorer already reads.

    python -m research.voice.export            # -> $SATYAPAN_VOICE_DATA/models/*.onnx
    python -m research.voice.export --install  # + copy to extension/models/ (= `make voice`)

model.onnx        input "input"  [1, n] raw 16 kHz mono float32 (normalised inside the graph)
                  output "output" [1, T, 1024] = XLS-R-300m layer-7 states
logreg_prob.onnx  input "X" [1, 1024] (mean over T) -> output "probabilities" [1, 2],
                  column 1 = P(synthetic) = sigmoid(standardise(X) . w + b)

This is the format of the Pascu et al. browser plug-in (extension/lib/onnx_scorer.js, the
desktop capture window, satyapan.voice.detector.OnnxVoiceDetector), so our licensed
re-training replaces the unlicensed files with no scorer code change. The head comes from
research/voice/bench.py (ours_head.json); check() compares both graphs with PyTorch.
"""

from __future__ import annotations

import json

import numpy as np

from research.voice.data import DATA, ROOT

OUT = DATA / "models"
MODEL, HEAD = OUT / "model.onnx", OUT / "logreg_prob.onnx"
HEAD_CONFIG = ROOT / "config" / "voice_head.json"


def export_trunk() -> None:
    import torch

    from research.voice.models import xlsr_trunk

    trunk = xlsr_trunk()

    class States(torch.nn.Module):  # the trunk without the mean pool
        def __init__(self) -> None:
            super().__init__()
            self.t = trunk

        def forward(self, wav: torch.Tensor) -> torch.Tensor:
            t = self.t
            wav = (wav - wav.mean(dim=1, keepdim=True)) / torch.sqrt(
                wav.var(dim=1, keepdim=True, unbiased=False) + 1e-7
            )
            h = t.feature_extractor(wav).transpose(1, 2)
            h, _ = t.feature_projection(h)
            h = h + t.pos_conv_embed(h)
            for layer in t.layers:
                out = layer(h)
                h = out[0] if isinstance(out, tuple) else out
            return h

    OUT.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        States().eval(), (torch.randn(1, 32000),), str(MODEL), input_names=["input"],
        output_names=["output"], dynamic_axes={"input": {1: "n"}, "output": {1: "t"}},
        opset_version=17, dynamo=False,
    )  # fmt: skip


def export_head() -> None:
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    head = _head()
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
    onnx.save(model, str(HEAD))


def check() -> None:
    """Both ONNX graphs against PyTorch (XLS-R trunk run in torch) + the head on 8 val clips."""
    import onnxruntime as ort
    import torch

    from research.voice.data import load
    from research.voice.models import xlsr_trunk

    head = _head()
    trunk = xlsr_trunk()
    m = ort.InferenceSession(str(MODEL), providers=["CPUExecutionProvider"])
    h = ort.InferenceSession(str(HEAD), providers=["CPUExecutionProvider"])
    mean, scale = np.array(head["mean"]), np.array(head["scale"])
    ref, got = [], []
    clips = load("val").audio[:8] if (DATA / "clips" / "val.npz").exists() else tones()
    for x in clips:
        with torch.inference_mode():
            e = trunk(torch.from_numpy(x[None, :].astype(np.float32)))[0].numpy()
        ref.append(float(((e - mean) / scale) @ np.array(head["coef"]) + head["intercept"]))
        states = m.run(None, {"input": x[None, :]})[0]
        p = h.run(None, {"X": states.mean(axis=1).astype(np.float32)})[0][0, 1]
        got.append(float(np.log(p / (1 - p))))
    diff = float(np.abs(np.array(got) - np.array(ref)).max())
    print(
        f"{MODEL.name} {MODEL.stat().st_size / 1e6:.0f} MB; max |logit diff| vs PyTorch {diff:.2e}"
    )
    if diff > 1e-2:
        raise SystemExit("ONNX export does not match PyTorch")


def tones() -> list[np.ndarray]:
    """Deterministic 3 s test signals (no benchmark data needed on a judge's laptop)."""
    t = np.arange(48000, dtype=np.float32) / 16000
    return [(0.1 * np.sin(2 * np.pi * f * t * (1 + 0.1 * t))).astype(np.float32)
            for f in (110, 180, 220, 330, 440, 660, 880, 1200)]  # fmt: skip


def _head() -> dict:
    """The fitted head: the benchmark's own file if present, else the committed copy."""
    f = DATA / "ours_head.json"
    return json.loads((f if f.exists() else HEAD_CONFIG).read_text())


def install() -> None:
    """Copy both files to where every scorer reads them (extension/models/) and commit-able
    head weights to config/voice_head.json (1,024 means, scales and weights: no audio)."""
    import shutil

    from satyapan.voice.detector import MODEL_DIR

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for f in (MODEL, HEAD):
        shutil.copyfile(f, MODEL_DIR / f.name)
    head = _head()
    keep = ("mean", "scale", "coef", "intercept", "C", "cv_auc_mean", "cv_auc_sd")
    out = {k: head[k] for k in keep}
    out["trained_on"] = "ASVspoof 2019 LA train, 1,500 bonafide + 1,500 spoof (ODC-By)"
    out["backbone"] = "facebook/wav2vec2-xls-r-300m layers 1-7, mean-pooled (Apache-2.0)"
    HEAD_CONFIG.write_text(json.dumps(out) + "\n")
    print(f"installed {MODEL.name} + {HEAD.name} in {MODEL_DIR}; head -> {HEAD_CONFIG}")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--install", action="store_true", help="also copy into extension/models")
    a = ap.parse_args()
    if not MODEL.exists():
        export_trunk()
    export_head()
    check()
    if a.install:
        install()


if __name__ == "__main__":
    main()
