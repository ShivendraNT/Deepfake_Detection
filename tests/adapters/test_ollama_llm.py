"""OllamaLLM request shape, offline (httpx.MockTransport — no socket is opened)."""

from __future__ import annotations

import json

import httpx
import pytest

from satyapan.adapters.ollama_llm import OllamaLLM
from satyapan.explain.prompt import SYSTEM_PROMPT
from satyapan.settings import Settings


def _llm(handler) -> OllamaLLM:  # type: ignore[no-untyped-def]
    return OllamaLLM(Settings(), client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_request_has_no_tools_and_constant_system_prompt() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        seen["path"] = request.url.path
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "ok [ev_x]."}})

    assert _llm(handler).complete(SYSTEM_PROMPT, '{"evidence": []}', 123) == "ok [ev_x]."
    assert seen["path"] == "/api/chat"
    assert "tools" not in seen and "format" not in seen and seen["stream"] is False
    messages = seen["messages"]
    assert isinstance(messages, list) and messages[0] == {
        "role": "system",
        "content": SYSTEM_PROMPT,
    }
    assert seen["options"] == {"temperature": 0, "num_predict": 123}


@pytest.mark.parametrize(
    "response",
    [httpx.Response(500, text="model not loaded"), httpx.Response(200, json={"error": "x"})],
)
def test_errors_raise_so_summarize_falls_back(response: httpx.Response) -> None:
    with pytest.raises((httpx.HTTPStatusError, KeyError, ValueError)):
        _llm(lambda _req: response).complete("s", "u", 10)
