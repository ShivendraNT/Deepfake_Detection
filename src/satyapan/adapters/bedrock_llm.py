"""Amazon Bedrock LLM client (Claude Haiku 4.5 via the `in.` India inference profile). TASK T15.

See docs/tasks/T15-llm-summary-faithfulness.md. The model ID comes from
SATYAPAN_BEDROCK_MODEL_ID (check the exact ID in the Bedrock console; do not hard-code).
The LLM gets NO tools. Its output is NEVER parsed back into signals.
"""

from __future__ import annotations

import boto3
from botocore.config import Config

from satyapan.settings import Settings


class BedrockLLM:
    """LLMClient using bedrock-runtime Converse API, 5 s timeout, no tools."""

    def __init__(self, settings: Settings) -> None:
        self.model_id = settings.bedrock_model_id
        if not self.model_id:
            raise ValueError("bedrock_model_id is not configured")

        self.client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region,
            config=Config(read_timeout=5, connect_timeout=5),
        )

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        response = self.client.converse(
            modelId=self.model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0},
        )
        return response["output"]["message"]["content"][0]["text"]
