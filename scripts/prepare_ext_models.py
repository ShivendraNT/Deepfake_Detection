"""Derive extension/models/logreg_prob.onnx from the hand-downloaded Pascu logreg.onnx.

onnxruntime-web cannot read the ZipMap output (`output_probability`, a sequence of maps), so we
drop the ZipMap node and expose the LinearClassifier's `probabilities` tensor [N, 2] instead.
Column 1 = P(synthetic). Output stays in extension/models/ (git-ignored, no redistribution).

Run: uv run --with onnx python scripts/prepare_ext_models.py
"""

from __future__ import annotations

from pathlib import Path

import onnx
from onnx import TensorProto, helper

MODELS = Path(__file__).resolve().parents[1] / "extension" / "models"


def main() -> None:
    model = onnx.load(MODELS / "logreg.onnx")
    graph = model.graph
    zipmaps = [n for n in graph.node if n.op_type == "ZipMap"]
    if len(zipmaps) != 1 or zipmaps[0].input[0] != "probabilities":
        raise ValueError("unexpected logreg.onnx graph: expected one ZipMap on 'probabilities'")
    graph.node.remove(zipmaps[0])
    for out in [o for o in graph.output if o.name == "output_probability"]:
        graph.output.remove(out)
    graph.output.append(
        helper.make_tensor_value_info("probabilities", TensorProto.FLOAT, [None, 2])
    )
    onnx.checker.check_model(model)
    onnx.save(model, MODELS / "logreg_prob.onnx")
    print(f"wrote {MODELS / 'logreg_prob.onnx'}")


if __name__ == "__main__":
    main()
