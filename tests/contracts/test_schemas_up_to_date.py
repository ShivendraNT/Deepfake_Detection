"""schemas/ must match the contracts. If this fails: run `make schemas` and commit."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_schemas_match_contracts() -> None:
    spec = importlib.util.spec_from_file_location(
        "export_schemas", ROOT / "scripts" / "export_schemas.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name, text in mod.build().items():
        on_disk = (ROOT / "schemas" / name).read_text(encoding="utf-8")
        assert on_disk == text, f"schemas/{name} is stale: run `make schemas`"
