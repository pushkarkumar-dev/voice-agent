"""Async client for the TTS service on the Windows box."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from shared.config import ServiceConfig


@dataclass
class Synthesis:
    wav_bytes: bytes
    server_ms: float
    audio_seconds: float
    model: str


class TTSClient:
    def __init__(self, cfg: ServiceConfig) -> None:
        self._http = httpx.AsyncClient(base_url=cfg.base_url, timeout=120.0)

    async def synthesize(self, text: str, voice: str | None = None) -> Synthesis:
        resp = await self._http.post("/synthesize", json={"text": text, "voice": voice})
        resp.raise_for_status()
        return Synthesis(
            wav_bytes=resp.content,
            server_ms=float(resp.headers.get("X-Duration-Ms", 0)),
            audio_seconds=float(resp.headers.get("X-Audio-Seconds", 0)),
            model=resp.headers.get("X-Model", ""),
        )

    async def aclose(self) -> None:
        await self._http.aclose()
