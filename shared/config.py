"""Typed access to shared/config.toml. Every service endpoint goes through
here — no host or port literals anywhere else in the codebase."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.toml"


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    model: str
    temperature: float
    max_tokens: int


@dataclass(frozen=True)
class ServiceConfig:
    base_url: str


@dataclass(frozen=True)
class Config:
    host: str
    llm: LLMConfig
    stt: ServiceConfig
    tts: ServiceConfig


def load_config(path: Path = CONFIG_PATH) -> Config:
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    host = os.environ.get("VOICEAGENT_HOST", raw["server"]["host"])

    def url(section: str) -> str:
        return f"http://{host}:{raw[section]['port']}"

    return Config(
        host=host,
        llm=LLMConfig(
            base_url=url("llm"),
            model=raw["llm"]["model"],
            temperature=raw["llm"]["temperature"],
            max_tokens=raw["llm"]["max_tokens"],
        ),
        stt=ServiceConfig(base_url=url("stt")),
        tts=ServiceConfig(base_url=url("tts")),
    )
