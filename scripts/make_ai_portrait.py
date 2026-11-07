"""Generate the dataset's AI 'officer' portrait with SD-Turbo (separate env: diffusers pins an
older huggingface_hub than the lab).

    uv venv ../sdenv --python 3.12 && uv pip install --python ../sdenv/bin/python \
        --index-url https://download.pytorch.org/whl/cpu torch
    uv pip install --python ../sdenv/bin/python "diffusers>=0.30" "transformers<4.50" \
        "huggingface_hub<1.0" accelerate invisible-watermark pillow numpy
    ../sdenv/bin/python scripts/make_ai_portrait.py ../satyapan-data/demo-build/portrait.png

Stability AI's SD 2.x reference scripts mark every output with invisible-watermark 'SDV2'
(dwtDct); the same is applied here so the file is what that reference pipeline produces.
"""

import json
import sys

import numpy as np
import torch
from diffusers import StableDiffusionPipeline
from imwatermark import WatermarkEncoder
from PIL import Image

SEED = 20261021
PROMPT = (
    "passport style studio portrait photograph of a stern middle-aged Indian man in a "
    "khaki police uniform, plain light grey background, sharp focus, 50mm photo"
)

out = sys.argv[1]
torch.set_num_threads(4)
pipe = StableDiffusionPipeline.from_pretrained(
    "stabilityai/sd-turbo", variant="fp16", torch_dtype=torch.float32
)
img = pipe(
    prompt=PROMPT,
    num_inference_steps=2,
    guidance_scale=0.0,
    height=512,
    width=512,
    generator=torch.Generator().manual_seed(SEED),
).images[0]
enc = WatermarkEncoder()
enc.set_watermark("bytes", b"SDV2")
bgr = np.ascontiguousarray(np.asarray(img)[..., ::-1])
marked = enc.encode(bgr, "dwtDct")[..., ::-1]
Image.fromarray(np.ascontiguousarray(marked)).save(out, format="PNG")
with open(out + ".json", "w") as fh:
    json.dump({"generator": f"SD-Turbo (stabilityai/sd-turbo), 2 steps, seed {SEED}", "prompt": PROMPT,
               "watermark": "invisible-watermark dwtDct 'SDV2'"}, fh)
print("wrote", out)
