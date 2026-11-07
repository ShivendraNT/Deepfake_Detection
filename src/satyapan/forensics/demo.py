"""Load the scripted demo case (data/forensics/demo, built by scripts/build_demo_dataset.py).

The case is re-created from the manifest: the scenario's FIR details, then every exhibit
through the normal intake path (hashing, write-once storage, custody log, analysis queue), so
the demo exercises exactly what a real case does. Reference samples are added first so that
cross-exhibit links resolve as soon as each questioned item finishes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from satyapan.forensics.models import EvidenceRole

DEMO_DIR = Path(__file__).resolve().parents[3] / "data" / "forensics" / "demo"


def load_demo_case(svc: Any, reset: bool = True, demo_dir: Path = DEMO_DIR) -> dict[str, Any]:
    manifest_path = demo_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("demo dataset not built: run `make demo-dataset`")
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    sc = dict(m["scenario"])
    case_id = sc.pop("id")
    existing = svc.store.case(case_id)
    if existing is not None and not reset:
        return svc.case_view(case_id)
    if existing is not None:
        svc.store.delete_case(case_id)
    svc.create_case(actor="demo-loader", id=case_id, demo=True, **sc)
    items = sorted(m["items"], key=lambda it: (it["role"] != "reference", it["file"]))
    for it in items:
        p = demo_dir / it["file"]
        if not p.exists():
            continue
        svc.add_evidence(case_id, p.read_bytes(), it["file"], actor="demo-loader",
                         role=EvidenceRole(it["role"]), description=it["description"],
                         received_from=it["received_from"])  # fmt: skip
    return svc.case_view(case_id)
