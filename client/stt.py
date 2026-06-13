"""Async client for the STT service on the Windows box."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from shared.config import ServiceConfig


@dataclass
class Transcript:
    text: str
    language: str
    audio_seconds: float
    server_ms: float
    model: str


class STTClient:
    def __init__(self, cfg: ServiceConfig) -> None:
        self._http = httpx.AsyncClient(base_url=cfg.base_url, timeout=60.0)

    async def transcribe(self, wav_bytes: bytes, language: str | None = None) -> Transcript:
        data = {"language": language} if language else {}
        resp = await self._http.post(
            "/transcribe",
            files={"audio": ("clip.wav", wav_bytes, "audio/wav")},
            data=data,
        )
        resp.raise_for_status()
        d = resp.json()
        return Transcript(
            text=d["text"],
            language=d["language"],
            audio_seconds=d["audio_seconds"],
            server_ms=d["duration_ms"],
            model=d["model"],
        )

    async def aclose(self) -> None:
        await self._http.aclose()
