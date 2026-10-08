"""Results provenance: nothing that writes into results/ may generate numbers with an RNG.

Background: results/INVALIDATED.md. A T18 script once drew "detector scores" from
random.gauss and wrote them to results/ as if measured. This static check makes that pattern
fail CI.

Rule: every .py file under research/ or scripts/ that refers to the results/ directory, and
every research.* module such a file imports (transitively), must not use `random` or
`numpy.random` -- EXCEPT seeded resampling (bootstrap CIs, speaker splits), allow-listed by
the comment `# provenance: seeded-resampling-ok` on the import line. Allow-listed files may
still only use seeded generators: `random.Random(<seed>)` / `np.random.default_rng(<seed>)`.
Module-level `random.gauss(...)` etc. (global, unseeded state) is never allowed.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALLOW = "# provenance: seeded-resampling-ok"
_WRITES_RESULTS = re.compile(r"""['"](?:\.\./)*results(?:/[^'"\n]*)?['"]""")


def writes_results(src: str) -> bool:
    return _WRITES_RESULTS.search(src) is not None


def _research_imports(tree: ast.AST) -> set[Path]:
    out: set[Path] = set()
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("research"):
            names = [node.module]
        elif isinstance(node, ast.Import):
            names = [a.name for a in node.names if a.name.startswith("research")]
        for name in names:
            base = ROOT / Path(*name.split("."))
            for cand in (base.with_suffix(".py"), base / "__init__.py"):
                if cand.exists():
                    out.add(cand)
    return out


def rng_violations(src: str) -> list[str]:
    """Return human-readable violations for one source file (empty list = clean)."""
    tree = ast.parse(src)
    lines = src.splitlines()
    bad: list[str] = []
    for node in ast.walk(tree):
        mods: list[str] = []
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [node.module or ""]
            if node.module == "numpy":
                mods += [f"numpy.{a.name}" for a in node.names]
        for m in mods:
            is_rng = m in ("random", "numpy.random") or m.startswith("numpy.random.")
            if is_rng and ALLOW not in lines[node.lineno - 1]:
                bad.append(f"line {node.lineno}: imports {m} without '{ALLOW}'")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        dotted = ast.unparse(node.func)
        if dotted.startswith("random.") or ".random." in f".{dotted}":
            fn = dotted.rsplit(".", 1)[-1]
            seeded_ctor = fn in ("Random", "default_rng", "RandomState") and (
                node.args or node.keywords
            )
            if not seeded_ctor:
                bad.append(f"line {node.lineno}: {dotted}(...) uses global/unseeded RNG")
    return bad


def results_producers() -> dict[Path, set[Path]]:
    """{writer script: set of files it pulls in from research/ (incl. itself)}."""
    files = [*(ROOT / "research").rglob("*.py"), *(ROOT / "scripts").rglob("*.py")]
    out: dict[Path, set[Path]] = {}
    for f in files:
        src = f.read_text(encoding="utf-8")
        if not writes_results(src):
            continue
        closure, todo = {f}, [f]
        while todo:
            cur = todo.pop()
            for dep in _research_imports(ast.parse(cur.read_text(encoding="utf-8"))):
                if dep not in closure:
                    closure.add(dep)
                    todo.append(dep)
        out[f] = closure
    return out


def test_no_rng_in_anything_that_writes_results() -> None:
    problems = []
    for writer, closure in results_producers().items():
        for f in sorted(closure):
            for v in rng_violations(f.read_text(encoding="utf-8")):
                problems.append(f"{f.relative_to(ROOT)} (via {writer.relative_to(ROOT)}): {v}")
    assert not problems, "\n".join(problems)


def test_checker_catches_the_withdrawn_t18_pattern() -> None:
    simulated = (
        "import random\n"
        "RESULTS = ROOT / 'results'\n"
        "rng = random.Random(42)\n"
        "score = rng.gauss(0.78, 0.12)\n"
    )
    assert writes_results(simulated)
    assert rng_violations(simulated)  # unlisted import


def test_checker_rejects_global_rng_even_when_allow_listed() -> None:
    src = f"import random  {ALLOW}\nx = random.gauss(0, 1)\n"
    assert any("unseeded" in v for v in rng_violations(src))
    ok = f"import random  {ALLOW}\nrng = random.Random(7)\n"
    assert rng_violations(ok) == []


def test_checker_handles_numpy() -> None:
    assert rng_violations("import numpy as np\nx = np.random.normal(0, 1)\n")
    assert rng_violations("from numpy import random\n")
    allowed = f"import numpy as np\nrng = np.random.default_rng(3)  {ALLOW}\n"
    assert rng_violations(allowed) == []


def test_results_dir_has_no_simulated_voice_numbers() -> None:
    assert (
        not (ROOT / "results" / "audio_eval.csv").exists()
        or (ROOT / "results" / "audio_eval_manifest.json").exists()
    ), "audio_eval.csv without a real-audio manifest (see results/INVALIDATED.md)"
