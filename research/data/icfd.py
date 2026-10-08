"""ICFD-31k loader using the OFFICIAL splits. TASK T19.

Data is downloaded MANUALLY (see docs/RESEARCH_PROTOCOL.md §Data) into research/_data/icfd/
which is git-ignored. License: defensive research only; no scam-script generation; no
commercial deployment without permission. Never commit ICFD text or paraphrases.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Split = Literal["train", "validation", "test", "cross_domain"]


@dataclass(frozen=True)
class Turn:
    speaker: str
    text: str


@dataclass(frozen=True)
class Conversation:
    conv_id: str
    split: Split
    label: int  # 1 = fraud, 0 = normal
    category: str  # fraud umbrella / normal
    turns: tuple[Turn, ...] = field(default_factory=tuple)

    @property
    def text(self) -> str:
        return "\n".join(f"{t.speaker}: {t.text}" for t in self.turns)


def load_icfd(root: Path, split: Split) -> list[Conversation]:
    """Read the split file(s) under `root` (official JSONL format). Return Conversations.
    Assert the split sizes match the paper (21000/4500/4500/1000) and print class balance.
    Field mapping:
      conv_id: conversation identifier
      label: 1 = fraud, 0 = normal
      category: fraud category / normal
      turns: list of turn dicts with 'speaker' and 'text'
    """
    candidates = [
        root / f"{split}.jsonl",
        root / f"{split}.json",
        root / split / f"{split}.jsonl",
    ]
    split_path: Path | None = None
    for c in candidates:
        if c.exists():
            split_path = c
            break
    if split_path is None:
        raise FileNotFoundError(f"Split file for '{split}' not found under {root}")

    convs = load_jsonl_conversations(split_path, split)
    expected_sizes: dict[Split, int] = {
        "train": 21000,
        "validation": 4500,
        "test": 4500,
        "cross_domain": 1000,
    }
    if split in expected_sizes:
        expected = expected_sizes[split]
        if len(convs) != expected:
            raise AssertionError(f"Expected {expected} conversations for {split}, got {len(convs)}")
    n_pos = sum(1 for c in convs if c.label == 1)
    n_neg = sum(1 for c in convs if c.label == 0)
    print(f"Loaded {len(convs)} conversations for {split}: {n_pos} fraud, {n_neg} normal")
    return convs


def load_jsonl_conversations(path: Path, split: Split) -> list[Conversation]:
    """Generic loader used by tests and by the external sets: one JSON object per line with
    keys conv_id, label, category, turns=[{speaker, text}, ...]."""
    convs: list[Conversation] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            data = json.loads(line_str)
            raw_turns = data.get("turns", [])
            turns = tuple(
                Turn(speaker=str(t.get("speaker", "")), text=str(t.get("text", "")))
                for t in raw_turns
            )
            convs.append(
                Conversation(
                    conv_id=str(data["conv_id"]),
                    split=split,
                    label=int(data["label"]),
                    category=str(data.get("category", "")),
                    turns=turns,
                )
            )
    return convs
