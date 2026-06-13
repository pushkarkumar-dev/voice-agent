"""Continuous mic capture -> VAD -> endpointer -> utterance events.

Always-open input stream in 512-sample blocks. A ~300ms pre-roll ring buffer
keeps the audio just before speech onset so the first word isn't clipped.
Emits ('start',) at speech onset and ('utterance', wav_bytes) at endpoint.
The sounddevice callback runs on its own thread; frames cross into asyncio
via a thread-safe queue.
"""

from __future__ import annotations

import asyncio
import collections
import io
import queue
import wave
from typing import AsyncIterator, Callable

import numpy as np
import sounddevice as sd

from client.endpointer import Endpointer, Event
from client.vad import WINDOW, SAMPLE_RATE, SileroVAD


class Listener:
    def __init__(
        self,
        vad: SileroVAD,
        endpointer: Endpointer,
        preroll_ms: int = 300,
        gate: Callable[[], bool] | None = None,
    ) -> None:
        """gate() -> bool: when it returns False, frames are skipped (used for
        half-duplex muting while the agent is speaking)."""
        self._vad = vad
        self._ep = endpointer
        self._gate = gate
        self._preroll = collections.deque(
            maxlen=max(1, round(preroll_ms / 1000 * SAMPLE_RATE / WINDOW))
        )
        self._frames: queue.Queue = queue.Queue()

    def _callback(self, indata, frames, time_info, status):
        self._frames.put(indata[:, 0].copy())

    async def events(self) -> AsyncIterator[tuple]:
        loop = asyncio.get_running_loop()
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16",
            blocksize=WINDOW, callback=self._callback,
        )
        capturing = False
        utter: list[np.ndarray] = []
        with stream:
            while True:
                frame = await loop.run_in_executor(None, self._frames.get)

                if self._gate is not None and not self._gate():
                    # half-duplex: ignore mic (and reset) while gated off
                    if capturing:
                        capturing = False
                        utter.clear()
                    self._preroll.clear()
                    self._ep.reset()
                    self._vad.reset()
                    continue

                self._preroll.append(frame)
                prob = self._vad.prob(frame)
                event = self._ep.update(prob)

                if capturing:
                    utter.append(frame)

                if event is Event.SPEECH_START:
                    capturing = True
                    utter = list(self._preroll)  # include pre-roll
                    yield ("start",)
                elif event is Event.UTTERANCE_END:
                    capturing = False
                    yield ("utterance", _to_wav(np.concatenate(utter)))
                    utter = []


def _to_wav(pcm: np.ndarray) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.astype(np.int16).tobytes())
    return buf.getvalue()
