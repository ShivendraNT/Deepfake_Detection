"""Write results/video_eval_manifest.json: every video the benchmark used, with its sha256,
label, identity cluster, split role and source. Re-running the benchmark on files with other
hashes is a different experiment (the manifest is how a reviewer can tell).

    python -m research.video.manifest
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from research.video.data import DATA, ROOT, SEED, dfdc_items, ffpp_items, sha256_file


def main() -> None:
    items = [i for i in ffpp_items() if i.split != "spare"] + dfdc_items()
    with ThreadPoolExecutor(4) as pool:
        digests = list(pool.map(lambda it: sha256_file(DATA / it.path), items))
    rows = [
        {"key": it.key, "path": it.path, "sha256": d, "label": it.label,
         "identity": it.identity, "split": it.split, "source": it.source, "method": it.method}
        for it, d in zip(items, digests, strict=True)
    ]  # fmt: skip
    meta = json.loads((ROOT / "models" / "video" / "blend_b0.json").read_text())
    splits = sorted({r["split"] for r in rows})
    out = {
        "seed": SEED,
        "sources": {
            "ffpp_c23": "HF gonnerthetooner/FaceForensics (copy of Kaggle xdxd003/ff-c23); "
            "official splits github.com/ondyari/FaceForensics dataset/splits",
            "dfdc": "HF gonnerthetooner/DFDC-extracted-full, train parts 0-2",
        },
        "blend_cnn_onnx_sha256": meta["onnx_sha256"],
        "counts": {s: sum(1 for r in rows if r["split"] == s) for s in splits},
        "items": rows,
    }
    path = ROOT / "results" / "video_eval_manifest.json"
    path.write_text(json.dumps(out, indent=0) + "\n")
    print(path, out["counts"])


if __name__ == "__main__":
    main()
