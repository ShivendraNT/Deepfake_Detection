"""Install the Forensic Lab's extra models (any OS). Run once with internet:

    uv run python scripts/forensics_models.py          # = make forensics-models
    uv run python scripts/forensics_models.py --verify # only report what is present

Downloads straight ONNX files where they exist (OpenCV SFace, WeSpeaker ResNet34) and exports
the selected AI-image classifier (config/aigen_model.json) to ONNX from its pinned Hugging Face
weights (needs torch + transformers once: `uv sync --extra forensics-build`). The face (GenD)
and voice (XLS-R) models come from `make video` and `make voice`; the speech engine from
`make asr`. Everything is written under models/ (git-ignored).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "models" / "forensics"
FILES = {
    "face_recognition_sface_2021dec.onnx": ("opencv/face_recognition_sface",
                                            "face_recognition_sface_2021dec.onnx", "Apache-2.0"),
    "speaker_resnet34.onnx": ("Wespeaker/wespeaker-voxceleb-resnet34-LM",
                              "voxceleb_resnet34_LM.onnx", "CC-BY-4.0"),
}  # fmt: skip


def download() -> None:
    from huggingface_hub import hf_hub_download

    OUT.mkdir(parents=True, exist_ok=True)
    for name, (repo, fname, lic) in FILES.items():
        dest = OUT / name
        if dest.exists():
            print(f"ok       {name}")
            continue
        print(f"download {name} ({repo}, {lic})")
        shutil.copy(hf_hub_download(repo, fname), dest)


def export_aigen() -> bool:
    spec = json.loads((ROOT / "config" / "aigen_model.json").read_text())
    dest = OUT / spec["file"]
    if dest.exists():
        print(f"ok       {spec['file']}")
        return True
    try:
        import torch
        from transformers import ViTForImageClassification
    except ImportError:
        print(f"MISSING  {spec['file']}: needs torch + transformers once "
              "(uv sync --extra forensics-build), then re-run")  # fmt: skip
        return False
    print(f"export   {spec['file']} from {spec['repo']}")
    net = ViTForImageClassification.from_pretrained(spec["repo"]).eval()

    class Wrap(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.net = net

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.net(pixel_values=x).logits

    x = torch.randn(1, 3, int(spec["size"]), int(spec["size"]))
    torch.onnx.export(Wrap().eval(), (x,), str(dest), input_names=["pixel_values"],
                      output_names=["logits"], dynamic_axes={"pixel_values": {0: "n"},
                      "logits": {0: "n"}}, opset_version=17, dynamo=False)  # fmt: skip
    import numpy as np
    import onnxruntime as ort

    with torch.inference_mode():
        ref = Wrap()(x).numpy()
    got = ort.InferenceSession(str(dest)).run(None, {"pixel_values": x.numpy()})[0]
    diff = float(np.abs(ref - got).max())
    print(f"         max |diff| vs PyTorch {diff:.2e}")
    if diff > 1e-3:
        dest.unlink()
        print("         REFUSED: export does not match PyTorch")
        return False
    return True


def warm_asr() -> None:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("SKIP     Whisper 'small' (no faster-whisper; run `make asr`)")
        return
    print("download Whisper 'small' for offline transcripts (once)")
    WhisperModel("small", device="cpu", compute_type="int8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if not args.verify:
        download()
        export_aigen()
        warm_asr()
    from satyapan.forensics.registry import registry

    st = registry().status()
    for k, v in st.items():
        print(f"{'ready  ' if v.get('available') else 'MISSING'}  {k:9s} {v.get('purpose', '')}")
    return 0 if all(v.get("available") for v in st.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
