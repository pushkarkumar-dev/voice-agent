"""Phase 2: streaming push-to-talk voice loop.

record -> STT -> [LLM stream -> sentencize] -> TTS per sentence -> play,
with synthesis and playback overlapping LLM generation. Headline metric is
time-to-first-audio (TTFA). Phase 1's client/voice.py is the non-streaming
baseline to compare against.

  uv run python -m client.voice_stream
"""

from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator

from client.audio import play_wav, record_push_to_talk
from client.chat import SYSTEM_PROMPT
from client.llm import LLMClient
from client.stt import STTClient
from client.tts import TTSClient
from shared.config import load_config
from shared.metrics import log_turn
from shared.text import sentencize

_SENTINEL = object()


async def _llm_producer(llm, history, sentence_q, marks) -> list[str]:
    """Stream the reply, split into sentences, enqueue them in order."""
    sentences: list[str] = []

    async def marked() -> AsyncIterator[str]:
        async for delta in llm.stream_complete(history):
            marks.setdefault("first_token", time.perf_counter())
            yield delta

    async for sentence in sentencize(marked()):
        marks.setdefault("first_sentence", time.perf_counter())
        sentences.append(sentence)
        await sentence_q.put(sentence)
    await sentence_q.put(_SENTINEL)
    return sentences


async def _tts_worker(tts, language, sentence_q, audio_q, marks) -> None:
    while True:
        sentence = await sentence_q.get()
        if sentence is _SENTINEL:
            break
        synth = await tts.synthesize(sentence, language=language)
        marks.setdefault("first_audio_ready", time.perf_counter())
        await audio_q.put(synth.wav_bytes)
    await audio_q.put(_SENTINEL)


async def _play_worker(audio_q, marks) -> None:
    loop = asyncio.get_running_loop()
    while True:
        wav = await audio_q.get()
        if wav is _SENTINEL:
            break
        marks.setdefault("first_audio_play", time.perf_counter())
        await loop.run_in_executor(None, play_wav, wav)


async def main() -> None:
    cfg = load_config()
    stt, llm, tts = STTClient(cfg.stt), LLMClient(cfg.llm), TTSClient(cfg.tts)
    history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    print(f"STT @ {cfg.stt.base_url} | LLM {cfg.llm.model} | TTS @ {cfg.tts.base_url}")
    print("Streaming push-to-talk — Ctrl-C to exit\n")

    try:
        while True:
            wav = record_push_to_talk()
            t0 = time.perf_counter()  # end of recording = start of voice-to-voice

            heard = await stt.transcribe(wav)
            t_stt = time.perf_counter()
            print(f"\nyou ({heard.language})> {heard.text}")
            history.append({"role": "user", "content": heard.text})

            sentence_q: asyncio.Queue = asyncio.Queue()
            audio_q: asyncio.Queue = asyncio.Queue()
            marks: dict[str, float] = {}

            producer = asyncio.create_task(
                _llm_producer(llm, history, sentence_q, marks))
            tts_task = asyncio.create_task(
                _tts_worker(tts, heard.language, sentence_q, audio_q, marks))
            play_task = asyncio.create_task(_play_worker(audio_q, marks))

            sentences = await producer
            await tts_task
            await play_task
            t_done = time.perf_counter()

            reply = " ".join(sentences)
            history.append({"role": "assistant", "content": reply})
            print(f"agent> {reply}")

            def ms(a: float, b: float) -> float:
                return round((b - a) * 1000, 1)

            ttfa = ms(t0, marks.get("first_audio_play", t_done))
            row = {
                "stt_ms": ms(t0, t_stt),
                "ttft_ms": ms(t_stt, marks.get("first_token", t_stt)),
                "tt_first_sentence_ms": ms(t_stt, marks.get("first_sentence", t_stt)),
                "ttfa_ms": ttfa,
                "total_ms": ms(t0, t_done),
            }
            print("  " + "  ".join(f"{k}={v}" for k, v in row.items()) + "\n")
            log_turn({
                "phase": "2-streaming",
                "transcript": heard.text,
                "stt_language": heard.language,
                "reply_text": reply,
                "llm_model": cfg.llm.model,
                **row,
            })
    except KeyboardInterrupt:
        pass
    finally:
        await asyncio.gather(stt.aclose(), llm.aclose(), tts.aclose())


if __name__ == "__main__":
    asyncio.run(main())
