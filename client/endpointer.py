"""Turn-taking state machine. Pure logic: per-frame speech probabilities in,
turn events out. No audio, no I/O — unit-testable with synthetic sequences.

Two states: SILENCE and SPEECH.
- In SILENCE, sustained speech (>= min_speech_ms above threshold) starts a turn
  and emits SPEECH_START.
- In SPEECH, sustained silence (>= silence_ms below threshold) ends the turn
  and emits UTTERANCE_END.
The debounce on entry rejects coughs/clicks; the trailing-silence window is the
main 'how long a pause ends my turn' feel knob.
"""

from __future__ import annotations

from enum import Enum, auto

# 512 samples @ 16kHz.
FRAME_MS = 512 / 16000 * 1000  # = 32.0


class Event(Enum):
    SPEECH_START = auto()
    UTTERANCE_END = auto()


class State(Enum):
    SILENCE = auto()
    SPEECH = auto()


class Endpointer:
    def __init__(
        self,
        threshold: float = 0.5,
        min_speech_ms: int = 200,
        silence_ms: int = 700,
        frame_ms: float = FRAME_MS,
    ) -> None:
        self.threshold = threshold
        self.frame_ms = frame_ms
        self._min_speech_frames = max(1, round(min_speech_ms / frame_ms))
        self._silence_frames = max(1, round(silence_ms / frame_ms))
        self.reset()

    def reset(self) -> None:
        self.state = State.SILENCE
        self._speech_run = 0
        self._silence_run = 0

    def update(self, prob: float) -> Event | None:
        """Feed one frame's speech probability; return an event or None."""
        is_speech = prob >= self.threshold

        if self.state is State.SILENCE:
            if is_speech:
                self._speech_run += 1
                if self._speech_run >= self._min_speech_frames:
                    self.state = State.SPEECH
                    self._silence_run = 0
                    return Event.SPEECH_START
            else:
                self._speech_run = 0
            return None

        # State.SPEECH
        if is_speech:
            self._silence_run = 0
        else:
            self._silence_run += 1
            if self._silence_run >= self._silence_frames:
                self.state = State.SILENCE
                self._speech_run = 0
                return Event.UTTERANCE_END
        return None
