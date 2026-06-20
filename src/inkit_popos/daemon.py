"""The dictation daemon: orchestrates record -> transcribe -> polish -> inject.

State machine (single IPC thread serializes commands):

    idle --start/toggle--> recording --stop/toggle--> processing --> idle

Transcription runs in a background worker so the IPC socket stays responsive.
"""
from __future__ import annotations

import sys
import threading
import time
from typing import Any, Dict, Optional

from . import notify as notify_mod
from .audio import Recorder
from .engines import build_engine
from .engines.base import SttEngine
from .inject import Injector
from .ipc import IpcServer
from .polish import polish_text
from .textproc import apply_replacements, apply_spoken_punctuation

STATE_IDLE = "idle"
STATE_RECORDING = "recording"
STATE_PROCESSING = "processing"


def _log(msg: str) -> None:
    print(f"[inkit-popos] {msg}", file=sys.stderr, flush=True)


class Daemon:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        audio_cfg = config.get("audio", {})
        self.recorder = Recorder(
            sample_rate=audio_cfg.get("sample_rate", 16000),
            channels=audio_cfg.get("channels", 1),
            device=audio_cfg.get("device"),
        )
        self.injector = Injector(method=config.get("inject", {}).get("method", "auto"))
        self.state = STATE_IDLE
        self._engine: Optional[SttEngine] = None
        self._engine_lock = threading.Lock()
        self._server = IpcServer(self._handle)

    # -- engine (lazy, cached) ----------------------------------------------

    def _get_engine(self) -> SttEngine:
        with self._engine_lock:
            if self._engine is None:
                self._engine = build_engine(self.config)
            return self._engine

    def _warmup(self) -> None:
        try:
            self._get_engine()
            _log(f"engine ready: {self.config.get('engine')}")
        except Exception as exc:  # noqa: BLE001 - reported lazily on first use
            _log(f"engine not ready yet: {exc}")

    # -- notifications -------------------------------------------------------

    def _notify(self, summary: str, body: str = "") -> None:
        notify_mod.notify(summary, body, enabled=self.config.get("notify", True))

    # -- command handling ----------------------------------------------------

    def _handle(self, command: str) -> str:
        cmd = command.strip().lower()
        if cmd == "ping":
            return "pong"
        if cmd == "status":
            return f"{self.state} engine={self.config.get('engine')}"
        if cmd == "start":
            return self._start()
        if cmd == "stop":
            return self._stop()
        if cmd == "cancel":
            return self._cancel()
        if cmd == "toggle":
            if self.state == STATE_RECORDING:
                return self._stop()
            if self.state == STATE_IDLE:
                return self._start()
            return "busy"
        if cmd == "quit":
            threading.Thread(target=self._shutdown, daemon=True).start()
            return "quitting"
        return f"unknown command: {command}"

    def _start(self) -> str:
        if self.state != STATE_IDLE:
            return self.state
        self.recorder.start()
        self.state = STATE_RECORDING
        self._notify("Listening…", "Speak now")
        _log("recording started")
        return "recording"

    def _stop(self) -> str:
        if self.state != STATE_RECORDING:
            return self.state
        audio = self.recorder.stop()
        self.state = STATE_PROCESSING
        _log(f"recording stopped ({audio.shape[0] / self.recorder.sample_rate:.1f}s)")
        threading.Thread(target=self._process, args=(audio,), daemon=True).start()
        return "processing"

    def _cancel(self) -> str:
        """Discard an in-progress recording without transcribing it."""
        if self.state != STATE_RECORDING:
            return self.state
        self.recorder.stop()  # drop the captured audio
        self.state = STATE_IDLE
        self._notify("InkIt", "Cancelled")
        _log("recording cancelled")
        return "cancelled"

    def _process(self, audio) -> None:
        try:
            engine = self._get_engine()
            text = engine.transcribe(audio, self.recorder.sample_rate)
            # Deterministic: spoken "comma"/"new line" -> symbols, before polish
            # so the LLM sees already-punctuated text and won't fight it.
            if text:
                text = apply_spoken_punctuation(text, self.config.get("punctuation", {}))
            polish_cfg = self.config.get("polish", {})
            if text and polish_cfg.get("enabled"):
                try:
                    text = polish_text(text, polish_cfg)
                except Exception as exc:  # noqa: BLE001 - polish is best-effort
                    _log(f"polish failed, using raw transcript: {exc}")
            # User substitution table runs last so it has the final say over
            # both the raw transcript and any polish rewrite.
            if text:
                text = apply_replacements(text, self.config.get("replacements", {}))
            if text:
                method = self.injector.inject_text(text)
                _log(f"injected via {method}: {text!r}")
                self._notify("InkIt", text[:120])
            else:
                _log("no speech detected")
                self._notify("InkIt", "No speech detected")
        except Exception as exc:  # noqa: BLE001
            _log(f"error: {exc}")
            self._notify("InkIt error", str(exc))
        finally:
            self.state = STATE_IDLE

    # -- lifecycle -----------------------------------------------------------

    def _shutdown(self) -> None:
        time.sleep(0.1)
        self._server.stop()

    def run(self) -> int:
        self._server.start()
        threading.Thread(target=self._warmup, daemon=True).start()
        _log(f"listening on {self._server.path}")
        self._notify("InkIt ready", f"engine: {self.config.get('engine')}")
        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            if self.recorder.is_recording:
                self.recorder.stop()
            self._server.stop()
        _log("stopped")
        return 0
