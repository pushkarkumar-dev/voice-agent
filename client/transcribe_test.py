"""Milestone 2 test: record on the Mac, transcribe on the Windows box.

  uv run python -m client.transcribe_test
"""

from __future__ import annotations

import asyncio

from client.audio import record_push_to_talk
from client.stt import STTClient
from shared.config import load_config
from shared.metrics import TurnTimer, log_turn


async def main() -> None:
    cfg = load_config()
    stt = STTClient(cfg.stt)
    print(f"STT @ {cfg.stt.base_url} — Ctrl-C to exit\n")

    try:
        while True:
            timer = TurnTimer()
            with timer.stage("record"):
                wav = record_push_to_talk()
            with timer.stage("stt"):
                t = await stt.transcribe(wav)

            print(f"\n[{t.language}] {t.text}\n")
            print(timer.table())
            print(f"  (server-side inference: {t.server_ms} ms "
                  f"for {t.audio_seconds}s of audio)\n")
            log_turn(
                {
                    "phase": "1-milestone-2",
                    "transcript": t.text,
                    "stt_language": t.language,
                    "stt_model": t.model,
                    "audio_seconds": t.audio_seconds,
                    "stt_server_ms": t.server_ms,
                    "stages_ms": timer.stages,
                    "total_ms": timer.total_ms,
                }
            )
    except KeyboardInterrupt:
        pass
    finally:
        await stt.aclose()


if __name__ == "__main__":
    asyncio.run(main())
