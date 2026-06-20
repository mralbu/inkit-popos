"""Local NVIDIA Parakeet (NeMo transducer) STT via sherpa-onnx.

Runs fully offline on CPU. Point ``model_dir`` at an unpacked sherpa-onnx
Parakeet model directory containing encoder/decoder/joiner ONNX files and a
``tokens.txt``. See the README for download instructions.
"""
from __future__ import annotations

import glob
import os
from typing import Tuple

import numpy as np

from .base import SttEngine


def _find_one(model_dir: str, *patterns: str) -> str:
    for pattern in patterns:
        matches = sorted(glob.glob(os.path.join(model_dir, pattern)))
        if matches:
            # Prefer non-int8 weights when several variants are present.
            non_int8 = [m for m in matches if "int8" not in os.path.basename(m)]
            return (non_int8 or matches)[0]
    raise FileNotFoundError(
        f"Could not find a model file matching {patterns} in {model_dir!r}"
    )


def _resolve_model_files(model_dir: str) -> Tuple[str, str, str, str]:
    encoder = _find_one(model_dir, "encoder*.onnx")
    decoder = _find_one(model_dir, "decoder*.onnx")
    joiner = _find_one(model_dir, "joiner*.onnx")
    tokens = _find_one(model_dir, "tokens.txt")
    return encoder, decoder, joiner, tokens


class ParakeetEngine(SttEngine):
    name = "parakeet"

    def __init__(
        self,
        model_dir: str,
        num_threads: int = 2,
        decoding_method: str = "greedy_search",
        provider: str = "cpu",
    ):
        try:
            import sherpa_onnx
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "The 'sherpa-onnx' package is not installed. "
                "Install it with: pip install 'inkit-popos[parakeet]'"
            ) from exc

        if not model_dir:
            raise RuntimeError("parakeet.model_dir is not set in the config.")
        model_dir = os.path.expanduser(model_dir)
        if not os.path.isdir(model_dir):
            raise RuntimeError(
                f"Parakeet model directory not found: {model_dir}\n"
                "Download a sherpa-onnx Parakeet model first (see the README)."
            )

        encoder, decoder, joiner, tokens = _resolve_model_files(model_dir)
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=encoder,
            decoder=decoder,
            joiner=joiner,
            tokens=tokens,
            num_threads=num_threads,
            sample_rate=16000,
            feature_dim=80,
            decoding_method=decoding_method,
            model_type="nemo_transducer",
            provider=provider,
        )

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        if audio.size == 0:
            return ""
        # The Parakeet ONNX graph can't handle long audio in one pass (its
        # self-attention overflows), so split long input at silences and decode
        # each chunk. Short utterances pass through unchanged as a single chunk.
        from ..audio import split_on_silence

        parts = []
        for chunk in split_on_silence(audio, sample_rate):
            stream = self._recognizer.create_stream()
            stream.accept_waveform(sample_rate, chunk)
            self._recognizer.decode_streams([stream])
            text = (stream.result.text or "").strip()
            if text:
                parts.append(text)
        return " ".join(parts).strip()
