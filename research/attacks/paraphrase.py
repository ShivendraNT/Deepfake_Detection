"""Paraphrase attack sets P0/P1/P2. TASK T20 (leader). Runs on Kaggle with vLLM.

BEFORE RUNNING: email the ICFD authors (docs/RESEARCH_PROTOCOL.md §License). Never commit or
release paraphrase TEXT. Store outputs under research/_data/attacks/ (git-ignored).
Prompts here are REDACTED templates: they describe a style transformation, not how to scam.
"""

from __future__ import annotations

from typing import Literal

Attack = Literal["P0", "P1", "P2"]

PROMPTS: dict[Attack, str] = {
    "P0": (
        "Rewrite the following conversation in different words. Keep every speaker, every "
        "fact and the meaning exactly the same. Output only the rewritten conversation."
    ),
    "P1": (
        "Rewrite the following conversation so that it sounds calm and polite. Remove urgency, "
        "threats and pressure words. Keep every request that any speaker makes, with the same "
        "details. Output only the rewritten conversation."
    ),
    "P2": (
        "Rewrite the following conversation so that every request is phrased indirectly, as a "
        "routine formality, without naming it explicitly. Keep the same details. Output only "
        "the rewritten conversation."
    ),
}


def build_prompt(attack: Attack, conversation_text: str) -> list[dict[str, str]]:
    """Chat messages: [{"role": "system", "content": PROMPTS[attack]},
    {"role": "user", "content": conversation_text}]. Raise ValueError on empty text."""
    raise NotImplementedError("T20: see docs/tasks/T20-research-paraphrase-attacks.md")


def generate_with_vllm(model: str, prompts: list[list[dict[str, str]]], seed: int = 0) -> list[str]:
    """Kaggle only: vllm.LLM(model, dtype="half", tensor_parallel_size=2).chat(...),
    temperature=0.7, top_p=0.9, max_tokens=600, seed=seed."""
    raise NotImplementedError("T20: see docs/tasks/T20-research-paraphrase-attacks.md")
