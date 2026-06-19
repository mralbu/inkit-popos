"""Cartesia Ink speech-to-text engine (cloud API).

Uses the official ``cartesia`` Python SDK's manual-finalize STT websocket,
which matches push-to-talk usage: stream the recorded PCM, send ``finalize``,
then collect the final transcript.
"""
from __future__ import annotations

import os

import numpy as np

from .base import SttEngine

# 50 ms of 16-bit mono PCM at 16 kHz; small chunks keep the socket responsive.
_CHUNK_BYTES = 1600


def _to_pcm_s16le(audio: np.ndarray) -> bytes:
    clipped = np.clip(audio, -1.0, 1.0)
    return (clipped * 32767.0).astype("<i2").tobytes()


class CartesiaEngine(SttEngine):
    name = "cartesia"

    def __init__(self, api_key=None, model="ink-whisper", language="en"):
        try:
            from cartesia import Cartesia
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "The 'cartesia' package is not installed. "
                "Install it with: pip install 'inkit-popos[cartesia]'"
            ) from exc

        api_key = api_key or os.environ.get("CARTESIA_API_KEY")
        if not api_key:
            raise RuntimeError(
                "No Cartesia API key. Set CARTESIA_API_KEY or cartesia.api_key in "
                "the config. Get a free key at https://cartesia.ai"
            )
        self._client = Cartesia(api_key=api_key)
        self.model = model
        self.language = language

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        if audio.size == 0:
            return ""
        pcm = _to_pcm_s16le(audio)

        kwargs = dict(
            model=self.model,
            language=self.language,
            encoding="pcm_s16le",
            sample_rate=sample_rate,
        )
        try:
            connection = self._client.stt.manual_finalize.websocket(**kwargs)
        except TypeError:
            # Older/newer SDKs may not accept `language`; retry without it.
            kwargs.pop("language", None)
            connection = self._client.stt.manual_finalize.websocket(**kwargs)

        parts = []
        with connection as conn:
            for i in range(0, len(pcm), _CHUNK_BYTES):
                conn.send_raw(pcm[i : i + _CHUNK_BYTES])
            conn.send("finalize")
            for event in conn:
                etype = getattr(event, "type", None)
                if etype == "transcript" and getattr(event, "is_final", False):
                    parts.append(getattr(event, "text", "") or "")
                elif etype in ("done", "flush_done"):
                    break
        return "".join(parts).strip()
