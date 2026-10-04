"""Only satyapan/adapters/ may import network libraries (AST check over src/)."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "satyapan"
NETWORK_MODULES = {
    "boto3",
    "botocore",
    "httpx",
    "requests",
    "urllib.request",
    "aiohttp",
    "socket",
    "http.client",
    "smtplib",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_network_imports_only_in_adapters() -> None:
    offenders = []
    for py in SRC.rglob("*.py"):
        if "adapters" in py.relative_to(SRC).parts:
            continue
        for name in _imports(py):
            if any(name == m or name.startswith(m + ".") for m in NETWORK_MODULES):
                offenders.append(f"{py.relative_to(SRC)} imports {name}")
    assert offenders == [], "move network code into satyapan/adapters/: " + "; ".join(offenders)
