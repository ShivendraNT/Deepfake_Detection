"""Local LLM client via Ollama (free, runs on the lead's Mac). TASK T15.

See docs/tasks/T15-llm-summary-faithfulness.md.
- Model name from SATYAPAN_LLM_MODEL (default "llama3.1:8b"); server from SATYAPAN_OLLAMA_URL
  (default "http://127.0.0.1:11434"); timeout settings.llm_timeout_s (default 30 s).
- POST {ollama_url}/api/chat with httpx, JSON body:
  {"model": settings.llm_model,
   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
   "stream": false, "options": {"temperature": 0, "num_predict": max_tokens}}
  Return response JSON ["message"]["content"].
- NO "tools" key, ever. The LLM gets no tools. Its output is NEVER parsed back into signals.
- HTTP error, timeout or bad JSON -> raise (summarize() then falls back to the template).
"""

from __future__ import annotations

import httpx

from satyapan.settings import Settings


class OllamaLLM:
    """LLMClient using the local Ollama /api/chat endpoint, no tools, no streaming."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.model = settings.llm_model
        self.url = settings.ollama_url.rstrip("/") + "/api/chat"
        self._client = client or httpx.Client(timeout=settings.llm_timeout_s)

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        body = {  # deliberately no "tools" / "format" keys: the model can only return text
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0, "num_predict": max_tokens},
        }
        r = self._client.post(self.url, json=body)
        r.raise_for_status()
        content = r.json()["message"]["content"]
        if not isinstance(content, str):
            raise ValueError("Ollama returned no text content")
        return content
