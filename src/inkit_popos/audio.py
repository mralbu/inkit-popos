"""Microphone capture and audio helpers built on PortAudio (sounddevice)."""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
from typing import List, Optional

import numpy as np


class Recorder:
    """Records mono float32 audio into a buffer between start() and stop().

    Capture runs in PortAudio's callback thread; start()/stop() are called from
    the daemon thread.
    """

    def __init__(self, sample_rate: int = 16000, channels: int = 1, device=None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self._frames: List[np.ndarray] = []
        self._stream = None
        self._lock = threading.Lock()

    def _callback(self, indata, frames, time_info, status):  # noqa: ARG002
        with self._lock:
            self._frames.append(indata.copy())

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        import sounddevice as sd

        with self._lock:
            self._frames = []
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            device=self.device,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        """Stop capture and return the recorded mono float32 waveform."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            frames = self._frames
            self._frames = []
        if not frames:
            return np.zeros(0, dtype=np.float32)
        data = np.concatenate(frames, axis=0)
        if data.ndim > 1:
            data = data[:, 0]
        return np.ascontiguousarray(data, dtype=np.float32)


def list_input_devices() -> List[dict]:
    import sounddevice as sd

    devices = []
    for idx, dev in enumerate(sd.query_devices()):
        if dev.get("max_input_channels", 0) > 0:
            devices.append({"index": idx, "name": dev["name"]})
    return devices


def load_audio(path: str, target_rate: int = 16000) -> np.ndarray:
    """Load an audio file as mono float32 resampled to ``target_rate``.

    Handles WAV, FLAC, OGG, MP3 and more. Reading goes through libsndfile
    (``soundfile``); for formats it can't decode — e.g. MP3 on older
    libsndfile builds — it falls back to ``ffmpeg`` if installed.
    """
    try:
        return _load_with_soundfile(path, target_rate)
    except Exception as exc:  # noqa: BLE001 - retry via ffmpeg below
        if shutil.which("ffmpeg"):
            return _load_with_ffmpeg(path, target_rate)
        ext = os.path.splitext(path)[1].lstrip(".").lower() or "audio"
        raise RuntimeError(
            f"Could not decode {ext!r} file {path!r}: {exc}. "
            "Install ffmpeg, or a newer 'soundfile' with MP3 support."
        ) from exc


# Backwards-compatible alias.
load_wav = load_audio


def _load_with_soundfile(path: str, target_rate: int) -> np.ndarray:
    import soundfile as sf

    data, sr = sf.read(path, dtype="float32", always_2d=True)
    data = data[:, 0]  # mono
    if sr != target_rate:
        data = _resample_linear(data, sr, target_rate)
    return np.ascontiguousarray(data, dtype=np.float32)


def _load_with_ffmpeg(path: str, target_rate: int) -> np.ndarray:
    """Decode any format ffmpeg supports to mono float32 at ``target_rate``."""
    cmd = [
        "ffmpeg", "-nostdin", "-loglevel", "error",
        "-i", path,
        "-f", "f32le", "-acodec", "pcm_f32le",
        "-ac", "1", "-ar", str(target_rate),
        "pipe:1",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    return np.frombuffer(proc.stdout, dtype="<f4").astype(np.float32)


def _resample_linear(samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate or samples.size == 0:
        return samples
    duration = samples.shape[0] / src_rate
    dst_len = int(round(duration * dst_rate))
    src_t = np.linspace(0.0, duration, num=samples.shape[0], endpoint=False)
    dst_t = np.linspace(0.0, duration, num=dst_len, endpoint=False)
    return np.interp(dst_t, src_t, samples).astype(np.float32)
