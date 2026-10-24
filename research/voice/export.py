"""Export our voice model in the two-file format every Satya scorer already reads.

    python -m research.voice.export      # -> $SATYAPAN_VOICE_DATA/models/{model,logreg_prob}.onnx

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

from research.voice.data import DATA

OUT = DATA / "models"
MODEL, HEAD = OUT / "model.onnx", OUT / "logreg_prob.onnx"


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

    head = json.loads((DATA / "ours_head.json").read_text())
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
    """Both graphs against PyTorch + the fitted head on real val clips."""
    import onnxruntime as ort

    from research.voice.bench import ours_scores
    from research.voice.data import load

    head = json.loads((DATA / "ours_head.json").read_text())
    m = ort.InferenceSession(str(MODEL), providers=["CPUExecutionProvider"])
    h = ort.InferenceSession(str(HEAD), providers=["CPUExecutionProvider"])
    val = load("val")
    ref = ours_scores("val", "clean", head)[:8]
    got = []
    for x in val.audio[:8]:
        states = m.run(None, {"input": x[None, :]})[0]
        p = h.run(None, {"X": states.mean(axis=1).astype(np.float32)})[0][0, 1]
        got.append(float(np.log(p / (1 - p))))
    diff = float(np.abs(np.array(got) - ref).max())
    print(
        f"{MODEL.name} {MODEL.stat().st_size / 1e6:.0f} MB; max |logit diff| vs PyTorch {diff:.2e}"
    )
    if diff > 1e-2:
        raise SystemExit("ONNX export does not match PyTorch")


def main() -> None:
    export_trunk()
    export_head()
    check()


if __name__ == "__main__":
    main()
