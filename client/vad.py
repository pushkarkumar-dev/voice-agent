"""Silero VAD wrapper. Runs on the Mac CPU; tiny and fast.

Speech probability per 512-sample (32ms @ 16kHz) frame. Silero is
speech-specific, not a plain energy gate — random noise stays low, only
voice spikes.
"""

from __future__ import annotations

import numpy as np

WINDOW = 512  # samples @ 16kHz, required by Silero v5/v6
SAMPLE_RATE = 16_000


class SileroVAD:
    def __init__(self) -> None:
        import torch
        from silero_vad import load_silero_vad

        self._torch = torch
        self.model = load_silero_vad()

    def reset(self) -> None:
        self.model.reset_states()

    def prob(self, frame_int16: np.ndarray) -> float:
        """Speech probability [0,1] for one 512-sample int16 frame."""
        x = (frame_int16.astype(np.float32) / 32768.0).reshape(-1)
        t = self._torch.from_numpy(x)
        with self._torch.no_grad():
            return self.model(t, SAMPLE_RATE).item()
