"""Task specs, task tests and the status board stay consistent (24 tasks)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / "docs" / "tasks"
IDS = [f"T{i:02d}" for i in range(1, 25)]
PATH_RE = (
    r"`((?:src|tests|docs|extension|console|research|results|figures|config|data|scripts|schemas)"
    r"/[^`\s]*)`"
)
REQUIRED_SECTIONS = [
    "## Goal",
    "## Owner",
    "## Depends on",
    "## Files to create or modify",
    "## Do not touch",
    "## Interfaces",
    "## Plan (steps)",
    "## Acceptance criteria",
    "## Test command",
    "## Definition of Done",
    "## Common mistakes",
    "## Hints and links",
    "## Agent plan (write yours here)",
]


def _spec(task_id: str) -> Path:
    found = sorted(TASKS.glob(f"{task_id}-*.md"))
    assert len(found) == 1, f"exactly one spec file for {task_id}, found {found}"
    return found[0]


def _section(text: str, heading: str) -> str:
    start = text.index(heading) + len(heading)
    nxt = text.find("\n## ", start)
    return text[start : nxt if nxt != -1 else len(text)]


@pytest.mark.parametrize("task_id", IDS)
def test_spec_has_all_sections(task_id: str) -> None:
    text = _spec(task_id).read_text(encoding="utf-8")
    for s in REQUIRED_SECTIONS:
        assert s in text, f"{task_id} spec missing section {s!r}"
    assert f"make task T={task_id}" in _section(text, "## Test command")


@pytest.mark.parametrize("task_id", IDS)
def test_listed_files_exist_unless_new(task_id: str) -> None:
    text = _spec(task_id).read_text(encoding="utf-8")
    for line in _section(text, "## Files to create or modify").splitlines():
        if "(new" in line:
            continue
        for path in re.findall(PATH_RE, line):
            p = path.rstrip("/")
            if any(ch in p for ch in "*<{"):
                continue
            assert (ROOT / p).exists(), (
                f"{task_id}: listed path {p} does not exist (mark it '(new)')"
            )


@pytest.mark.parametrize("task_id", IDS)
def test_each_task_has_acceptance_tests(task_id: str) -> None:
    files = list((ROOT / "tests" / "tasks").glob(f"test_{task_id.lower()}_*.py"))
    assert len(files) == 1, f"{task_id} needs exactly one tests/tasks/test_{task_id.lower()}_*.py"
    assert f'pytest.mark.task("{task_id}")' in files[0].read_text(encoding="utf-8")


def test_status_board_lists_every_task_once() -> None:
    status = (ROOT / "docs" / "STATUS.md").read_text(encoding="utf-8")
    for t in IDS:
        rows = [ln for ln in status.splitlines() if ln.startswith(f"| {t} |")]
        assert len(rows) == 1, f"{t} must appear exactly once in STATUS.md"
        spec_name = _spec(t).name
        assert spec_name in rows[0], f"{t} STATUS row must link {spec_name}"


def test_every_spec_reference_in_repo_exists() -> None:
    pattern = re.compile(r"docs/tasks/(T\d{2}-[a-z0-9\-]+\.md)")
    roots = [
        ROOT / "src",
        ROOT / "research",
        ROOT / "extension",
        ROOT / "console" / "src",
        ROOT / "docs",
        ROOT / "tests",
    ]
    missing = set()
    for r in roots:
        for p in r.rglob("*"):
            if p.is_file() and p.suffix in {".py", ".md", ".js", ".mjs", ".html", ".tsx", ".ts"}:
                for name in pattern.findall(p.read_text(encoding="utf-8", errors="ignore")):
                    if not (TASKS / name).exists():
                        missing.add(f"{p.relative_to(ROOT)} -> {name}")
    assert not missing, sorted(missing)


def test_stub_messages_point_to_their_own_task() -> None:
    bad = []
    for p in list((ROOT / "src").rglob("*.py")) + list((ROOT / "research").rglob("*.py")):
        for m in re.finditer(
            r'NotImplementedError\("(T\d{2}): see docs/tasks/(T\d{2})-',
            p.read_text(encoding="utf-8"),
        ):
            if m.group(1) != m.group(2):
                bad.append(f"{p.relative_to(ROOT)}: {m.group(0)}")
    assert not bad, bad
