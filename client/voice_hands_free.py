"""Phase 3: hands-free voice loop. No keys — Silero VAD + endpointing decide
when you've finished talking; optional barge-in lets you cut the agent off.

  uv run python -m client.voice_hands_free              # half-duplex (speakers)
  uv run python -m client.voice_hands_free --barge-in   # barge-in (headphones)

Half-duplex mutes the mic while the agent speaks (robust on speakers, no
barge-in). Barge-in keeps the mic live so talking over the agent interrupts it
— use headphones, or the agent's own voice echoes back and self-interrupts.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from typing import AsyncIterator

from client.chat import SYSTEM_PROMPT
from client.endpointer import Endpointer
from client.listener import Listener
from client.llm import LLMClient
from client.player import Player
from client.stt import STTClient
from client.tts import TTSClient
from client.vad import SileroVAD
from shared.config import load_config
from shared.metrics import log_turn
from shared.text import sentencize


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--barge-in", action="store_true",
                    help="keep mic live during playback (use headphones)")
    args = ap.parse_args()

    cfg = load_config()
    stt, llm, tts = STTClient(cfg.stt), LLMClient(cfg.llm), TTSClient(cfg.tts)
    player = Player()
    history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    vad = SileroVAD()
    endpointer = Endpointer()
    # half-duplex: gate the mic off while the agent is speaking
    gate = None if args.barge_in else (lambda: not player.is_playing)
    listener = Listener(vad, endpointer, gate=gate)

    mode = "barge-in" if args.barge_in else "half-duplex"
    print(f"STT @ {cfg.stt.base_url} | LLM {cfg.llm.model} | TTS @ {cfg.tts.base_url}")
    print(f"Hands-free ({mode}) — just talk. Ctrl-C to exit.\n")

    current: asyncio.Task | None = None

    async def respond(wav: bytes) -> None:
        t0 = time.perf_counter()
        heard = await stt.transcribe(wav)
        if not heard.text.strip():
            return
        print(f"\nyou ({heard.language})> {heard.text}")
        history.append({"role": "user", "content": heard.text})

        spoken: list[str] = []
        first_audio: float | None = None
        try:
            async for sentence in sentencize(llm.stream_complete(history)):
                synth = await tts.synthesize(sentence, language=heard.language)
                if first_audio is None:
                    first_audio = time.perf_counter()
                player.enqueue(synth.wav_bytes)
                spoken.append(sentence)
        finally:
            if spoken:
                reply = " ".join(spoken)
                history.append({"role": "assistant", "content": reply})
                print(f"agent> {reply}")
                log_turn({
                    "phase": "3-hands-free",
                    "mode": mode,
                    "transcript": heard.text,
                    "stt_language": heard.language,
                    "reply_text": reply,
                    "ttfa_ms": round(((first_audio or t0) - t0) * 1000, 1),
                    "total_ms": round((time.perf_counter() - t0) * 1000, 1),
                })

    def interrupt() -> None:
        nonlocal current
        if current and not current.done():
            current.cancel()
        player.stop()

    try:
        async for event in listener.events():
            if event[0] == "start" and args.barge_in:
                # user started talking over the agent -> shut up immediately
                if current and not current.done():
                    print("  [barge-in]")
                    interrupt()
            elif event[0] == "utterance":
                interrupt()  # cancel any in-flight reply, then answer this one
                current = asyncio.create_task(respond(event[1]))
    except KeyboardInterrupt:
        pass
    finally:
        interrupt()
        await asyncio.gather(stt.aclose(), llm.aclose(), tts.aclose())


if __name__ == "__main__":
    asyncio.run(main())
