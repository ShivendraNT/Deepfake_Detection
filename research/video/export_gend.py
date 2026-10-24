"""Export GenD (CLIP ViT-L/14, MIT, yermandy/GenD_CLIP_L_14) to ONNX for the product CNN slot.

    python -m research.video.export_gend            # -> DATA/models/gend_clip_l14.onnx

The graph takes the same input as our own blend CNN (ImageNet-normalised 224 px crops, NCHW)
and re-normalises to CLIP statistics inside, so satyapan.video.cnn.BlendScorer runs either
file unchanged. Output: one fake-logit per crop (logit_fake - logit_real); it matches the
PyTorch model to < 1e-5. ONNX Runtime int8 dynamic quantisation was tried and rejected: on 24
val crops its logits correlated only r = 0.92 with fp32 (0.98 with fc2 left in fp32), so it
would not be the model we benchmarked. We ship fp32 or nothing.
"""

from __future__ import annotations

import argparse

import numpy as np

from research.video.data import DATA
from research.video.hf_baselines import CLIP_MEAN, CLIP_STD, IMAGENET_MEAN, IMAGENET_STD

OUT = DATA / "models"
FP32 = OUT / "gend_clip_l14.onnx"


def build():
    import torch
    import torch.nn.functional as F
    from transformers import CLIPVisionConfig, CLIPVisionModel

    from research.video.hf_baselines import BY_NAME, _download, _state

    e = BY_NAME["gend_clip_l14"]
    path = _download(e.repo, e.revision, "model.safetensors")
    cfg = CLIPVisionConfig(
        hidden_size=1024, intermediate_size=4096, num_hidden_layers=24, num_attention_heads=16,
        patch_size=14, image_size=224, projection_dim=768, hidden_act="quick_gelu",
        layer_norm_eps=1e-5,
    )  # fmt: skip
    tower = CLIPVisionModel(cfg)
    vision = getattr(tower, "vision_model", tower).eval()
    vision.load_state_dict(_state(path, "feature_extractor.vision_model."), strict=False)
    head = _state(path, "model.linear.")

    class GenDLogit(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.vision = vision
            w = head["weight"]
            self.register_buffer("w", (w[1] - w[0]).reshape(-1, 1))
            self.register_buffer("b", (head["bias"][1] - head["bias"][0]).reshape(1))
            im_m, im_s = torch.tensor(IMAGENET_MEAN), torch.tensor(IMAGENET_STD)
            cl_m, cl_s = torch.tensor(CLIP_MEAN), torch.tensor(CLIP_STD)
            # x_clip = (x_im * im_s + im_m - cl_m) / cl_s  ==  x_im * scale + shift
            self.register_buffer("scale", (im_s / cl_s).view(1, 3, 1, 1))
            self.register_buffer("shift", ((im_m - cl_m) / cl_s).view(1, 3, 1, 1))

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            x = x * self.scale + self.shift
            z = F.normalize(self.vision(pixel_values=x).pooler_output, p=2, dim=1)
            return z @ self.w + self.b

    return GenDLogit().eval()


def export() -> None:
    import torch

    OUT.mkdir(parents=True, exist_ok=True)
    model = build()
    x = torch.randn(2, 3, 224, 224)
    torch.onnx.export(
        model, (x,), str(FP32), input_names=["input"], output_names=["logit"],
        dynamic_axes={"input": {0: "n"}, "logit": {0: "n"}}, opset_version=17, dynamo=False,
    )  # fmt: skip
    check(model)


def check(model=None) -> None:
    """The ONNX graph must agree with PyTorch (max |diff| < 1e-3 on random input)."""
    import onnxruntime as ort
    import torch

    model = model or build()
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, (3, 3, 224, 224)).astype(np.float32)
    with torch.inference_mode():
        ref = model(torch.from_numpy(x)).numpy().ravel()
    sess = ort.InferenceSession(str(FP32), providers=["CPUExecutionProvider"])
    diff = float(np.abs(sess.run(None, {"input": x})[0].ravel() - ref).max())
    print(FP32.name, f"{FP32.stat().st_size / 1e6:.0f} MB, max |diff| vs PyTorch {diff:.2e}")
    if diff > 1e-3:
        raise SystemExit("ONNX export does not match PyTorch")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        check()
    else:
        export()


if __name__ == "__main__":
    main()
