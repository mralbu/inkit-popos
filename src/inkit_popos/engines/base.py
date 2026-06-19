"""Common STT engine interface."""
from __future__ import annotations

import numpy as np


class SttEngine:
    """Transcribe a mono float32 waveform to text.

    Implementations should be safe to call repeatedly from a single worker
    thread; they own any network/model resources.
    """

    name = "base"

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - optional cleanup hook
        pass
