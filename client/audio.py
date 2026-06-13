"""Mic capture on the Mac. 16kHz mono int16 — what every STT model wants.

Push-to-talk for Phase 1: Enter starts the recording, Enter stops it.
VAD-driven capture replaces this in Phase 3.
"""

from __future__ import annotations

import io
import threading
import wave

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000
CHANNELS = 1


def record_push_to_talk() -> bytes:
    """Block until the user records a clip; returns wav-encoded bytes."""
    input("press Enter to start recording...")
    chunks: list[np.ndarray] = []
    stop = threading.Event()

    def callback(indata, frames, time_info, status):
        if status:
            print(f"[audio] {status}")
        chunks.append(indata.copy())

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        callback=callback,
    )
    waiter = threading.Thread(target=lambda: (input(), stop.set()))
    with stream:
        print("recording... press Enter to stop")
        waiter.start()
        stop.wait()

    pcm = np.concatenate(chunks) if chunks else np.empty((0, 1), dtype=np.int16)
    return _pcm_to_wav(pcm.tobytes())


def play_wav(wav_bytes: bytes) -> None:
    """Blocking playback of wav bytes (any sample rate the file declares)."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        rate = w.getframerate()
        channels = w.getnchannels()
        frames = w.readframes(w.getnframes())
    pcm = np.frombuffer(frames, dtype=np.int16).reshape(-1, channels)
    sd.play(pcm, samplerate=rate, blocking=True)


def _pcm_to_wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(2)  # int16
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()
