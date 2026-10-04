"""Agent harness files use only documented fields and keep the safety permissions."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OPENCODE_AGENT_FIELDS = {
    "description",
    "mode",
    "model",
    "temperature",
    "top_p",
    "steps",
    "disable",
    "hidden",
    "color",
    "prompt",
    "permission",
}
OPENCODE_COMMAND_FIELDS = {"description", "agent", "model", "subtask"}
CLAUDE_AGENT_REQUIRED = {"name", "description"}


def _frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} must start with YAML frontmatter"
    end = text.index("\n---", 4)
    fm = text[4:end]
    top = {}
    for line in fm.splitlines():
        m = re.match(r"^([A-Za-z_\-]+):\s*(.*)$", line)
        if m:
            top[m.group(1)] = m.group(2)
    return top, fm


def test_opencode_json_valid() -> None:
    cfg = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))
    assert cfg["$schema"] == "https://opencode.ai/config.json"
    bash = cfg["permission"]["bash"]
    assert bash["git push*"] == "deny" and bash["rm -rf*"] == "deny"
    assert cfg["permission"]["edit"]["src/satyapan/contracts/*"] in ("ask", "deny")
    assert cfg["permission"]["edit"]["tests/invariants/*"] in ("ask", "deny")
    assert cfg["permission"]["read"]["*.env"] == "deny"
    assert "model" not in cfg, "do not hard-code a (free) model id; pick one with /models"
    for f in cfg.get("instructions", []):
        assert (ROOT / f).exists()


@pytest.mark.parametrize(
    "path", sorted((ROOT / ".opencode" / "agents").glob("*.md")), ids=lambda p: p.name
)
def test_opencode_agents(path: Path) -> None:
    top, fm = _frontmatter(path)
    assert set(top) <= OPENCODE_AGENT_FIELDS, f"unknown fields {set(top) - OPENCODE_AGENT_FIELDS}"
    assert top.get("description")
    assert top.get("mode") in {"primary", "subagent", "all"}
    assert "model" not in top, "leave model unset: free model ids change"
    if "bash:" in fm:
        default_deny = re.search(r'bash:\n\s+"\*": deny', fm) is not None
        assert '"git push*": deny' in fm or "bash: deny" in fm or default_deny
    if path.stem in {
        "implementer",
        "tester",
        "planner",
        "reviewer",
        "researcher-eval",
        "docs-pitch",
    }:
        assert '"tests/invariants/*": deny' in fm or "edit: deny" in fm or '"*": deny' in fm


@pytest.mark.parametrize(
    "path", sorted((ROOT / ".opencode" / "commands").glob("*.md")), ids=lambda p: p.name
)
def test_opencode_commands(path: Path) -> None:
    top, _ = _frontmatter(path)
    assert set(top) <= OPENCODE_COMMAND_FIELDS
    assert top.get("description")
    if "agent" in top:
        assert (ROOT / ".opencode" / "agents" / f"{top['agent']}.md").exists()


def test_core_agents_present() -> None:
    names = {p.stem for p in (ROOT / ".opencode" / "agents").glob("*.md")}
    assert {"implementer", "reviewer"} <= names


@pytest.mark.parametrize(
    "path", sorted((ROOT / ".claude" / "agents").glob("*.md")), ids=lambda p: p.name
)
def test_claude_agents(path: Path) -> None:
    top, _ = _frontmatter(path)
    assert set(top) >= CLAUDE_AGENT_REQUIRED
    assert top["name"] == path.stem


def test_pointer_files() -> None:
    assert (ROOT / "CLAUDE.md").read_text(encoding="utf-8").startswith("@AGENTS.md")
    assert "@./AGENTS.md" in (ROOT / "GEMINI.md").read_text(encoding="utf-8")
    assert "AGENTS.md" in (ROOT / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
    for toml in (ROOT / ".gemini" / "commands").glob("*.toml"):
        t = toml.read_text(encoding="utf-8")
        assert "prompt = " in t and "description = " in t
