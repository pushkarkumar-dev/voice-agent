"""Interruptible audio playback. Unlike Phase 2's blocking play_wav, this can
be stopped instantly (for barge-in) and reports whether it's currently
playing. Plays queued wav clips back-to-back in a background thread."""

from __future__ import annotations

import io
import queue
import threading
import wave

import numpy as np
import sounddevice as sd

_STOP = object()


class Player:
    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue()
        self._playing = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    @property
    def is_playing(self) -> bool:
        return self._playing.is_set() or not self._q.empty()

    def enqueue(self, wav_bytes: bytes) -> None:
        self._q.put(wav_bytes)

    def stop(self) -> None:
        """Abort current clip and drop anything queued (barge-in)."""
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass
        sd.stop()
        self._playing.clear()

    def _run(self) -> None:
        while True:
            item = self._q.get()
            if item is _STOP:
                return
            with wave.open(io.BytesIO(item), "rb") as w:
                rate = w.getframerate()
                ch = w.getnchannels()
                pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
            self._playing.set()
            try:
                sd.play(pcm.reshape(-1, ch), samplerate=rate)
                sd.wait()  # interrupted by sd.stop() from another thread
            finally:
                self._playing.clear()
