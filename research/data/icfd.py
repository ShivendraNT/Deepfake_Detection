"""ICFD-31k loader using the OFFICIAL splits. TASK T19.

Data is downloaded MANUALLY (see docs/RESEARCH_PROTOCOL.md §Data) into research/_data/icfd/
which is git-ignored. License: defensive research only; no scam-script generation; no
commercial deployment without permission. Never commit ICFD text or paraphrases.
"""

from __future__ import annotations

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
    """Read the split file(s) under `root` (format: whatever the official release uses —
    inspect it first and document the field mapping in this docstring). Return Conversations.
    Assert the split sizes match the paper (21000/4500/4500/1000) and print class balance."""
    raise NotImplementedError("T19: see docs/tasks/T19-research-baselines-metrics.md")


def load_jsonl_conversations(path: Path, split: Split) -> list[Conversation]:
    """Generic loader used by tests and by the external sets: one JSON object per line with
    keys conv_id, label, category, turns=[{speaker, text}, ...]."""
    raise NotImplementedError("T19: see docs/tasks/T19-research-baselines-metrics.md")
