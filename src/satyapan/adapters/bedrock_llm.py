"""Amazon Bedrock LLM client (Claude Haiku 4.5 via the `in.` India inference profile). TASK T15.

See docs/tasks/T15-llm-summary-faithfulness.md. The model ID comes from
SATYAPAN_BEDROCK_MODEL_ID (check the exact ID in the Bedrock console; do not hard-code).
The LLM gets NO tools. Its output is NEVER parsed back into signals.
"""

from __future__ import annotations

from satyapan.settings import Settings


class BedrockLLM:
    """LLMClient using bedrock-runtime Converse API, 5 s timeout, no tools."""

    def __init__(self, settings: Settings) -> None:
        raise NotImplementedError("T15: see docs/tasks/T15-llm-summary-faithfulness.md")

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        raise NotImplementedError("T15: see docs/tasks/T15-llm-summary-faithfulness.md")
