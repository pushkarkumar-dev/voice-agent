"""Milestone 4: the full Phase 1 walking skeleton.

Push-to-talk: record on the Mac -> STT -> LLM -> TTS (all on the Windows
box) -> play the reply. Sequential and non-streaming by design; Phase 2
overlaps the stages.

  uv run python -m client.voice
"""

from __future__ import annotations

import asyncio

from client.audio import play_wav, record_push_to_talk
from client.chat import SYSTEM_PROMPT
from client.llm import LLMClient
from client.stt import STTClient
from client.tts import TTSClient
from shared.config import load_config
from shared.metrics import TurnTimer, log_turn


async def main() -> None:
    cfg = load_config()
    stt, llm, tts = STTClient(cfg.stt), LLMClient(cfg.llm), TTSClient(cfg.tts)
    history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    print(f"STT @ {cfg.stt.base_url} | LLM {cfg.llm.model} | TTS @ {cfg.tts.base_url}")
    print("Push-to-talk voice chat — Ctrl-C to exit\n")

    try:
        while True:
            timer = TurnTimer()
            with timer.stage("record"):
                wav = record_push_to_talk()
            with timer.stage("stt"):
                heard = await stt.transcribe(wav)
            print(f"\nyou ({heard.language})> {heard.text}")

            history.append({"role": "user", "content": heard.text})
            with timer.stage("llm"):
                completion = await llm.complete(history)
            history.append({"role": "assistant", "content": completion.text})
            print(f"agent> {completion.text}\n")

            with timer.stage("tts"):
                speech = await tts.synthesize(completion.text)
            with timer.stage("play"):
                play_wav(speech.wav_bytes)

            print(timer.table())
            # voice-to-voice as Phase 1 can measure it: everything after the
            # recording ends until playback starts (play stage excluded)
            v2v = sum(ms for name, ms in timer.stages.items()
                      if name not in ("record", "play"))
            print(f"  {'voice-to-voice':<12} {v2v:>8.1f} ms\n")
            log_turn(
                {
                    "phase": "1-milestone-4",
                    "transcript": heard.text,
                    "stt_language": heard.language,
                    "reply_text": completion.text,
                    "llm_model": completion.model,
                    "tts_model": speech.model,
                    "tts_audio_seconds": speech.audio_seconds,
                    "stages_ms": timer.stages,
                    "voice_to_voice_ms": round(v2v, 1),
                    "total_ms": timer.total_ms,
                }
            )
    except KeyboardInterrupt:
        pass
    finally:
        await asyncio.gather(stt.aclose(), llm.aclose(), tts.aclose())


if __name__ == "__main__":
    asyncio.run(main())
