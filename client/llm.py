"""Thin async client for any OpenAI-compatible chat endpoint (LM Studio now,
vLLM in Phase 5). Raw httpx on purpose — no SDK between us and the wire."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import AsyncIterator

import httpx

from shared.config import LLMConfig


@dataclass
class Completion:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int


class LLMClient:
    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg
        self._http = httpx.AsyncClient(base_url=cfg.base_url, timeout=120.0)

    async def complete(self, messages: list[dict]) -> Completion:
        resp = await self._http.post(
            "/v1/chat/completions",
            json={
                "model": self.cfg.model,
                "messages": messages,
                "temperature": self.cfg.temperature,
                "max_tokens": self.cfg.max_tokens,
                "stream": False,  # streaming lands in Phase 2
            },
        )
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        return Completion(
            text=data["choices"][0]["message"]["content"].strip(),
            model=data.get("model", self.cfg.model),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )

    async def stream_complete(self, messages: list[dict]) -> AsyncIterator[str]:
        """Yield content deltas as the model generates them (SSE)."""
        async with self._http.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": self.cfg.model,
                "messages": messages,
                "temperature": self.cfg.temperature,
                "max_tokens": self.cfg.max_tokens,
                "stream": True,
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if payload == "[DONE]":
                    break
                delta = json.loads(payload)["choices"][0]["delta"].get("content")
                if delta:
                    yield delta

    async def aclose(self) -> None:
        await self._http.aclose()
