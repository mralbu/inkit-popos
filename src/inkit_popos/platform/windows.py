"""Windows backend.

Mirrors the Linux seams with Windows-native mechanisms:

* **Injection** - ``SendInput`` Unicode keystrokes via ``ctypes`` (no extra
  dependency; types into the focused window like a keyboard would).
* **IPC** - a loopback TCP socket. Wayland's AF_UNIX socket isn't the right fit
  on Windows, so the daemon binds ``127.0.0.1:<ephemeral>`` and writes the port
  to a file the CLI reads. This is what makes ``inkit-popos toggle`` work.
* **Notifications** - best-effort no-op for now (degrades like Linux does when
  ``notify-send`` is absent).

A global hotkey listener is intentionally out of scope for this step; bind a
shortcut to ``inkit-popos toggle`` (or run it however you like) and the toggle
path works.

This module is only imported on Windows, but it imports cleanly on other
platforms too (the ``ctypes.windll`` calls happen lazily inside the injector),
so the Linux test suite can exercise the non-OS-specific parts.
"""
from __future__ import annotations

import ctypes
import os
import socket
from pathlib import Path
from typing import Callable, List

from .base import Backend, Injector, IpcServer


# --------------------------------------------------------------------------- #
# Text injection: SendInput Unicode keystrokes
# --------------------------------------------------------------------------- #

_PUL = ctypes.POINTER(ctypes.c_ulong)


class _KeyBdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", _PUL),
    ]


class _MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", _PUL),
    ]


class _HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort),
    ]


class _InputI(ctypes.Union):
    _fields_ = [("ki", _KeyBdInput), ("mi", _MouseInput), ("hi", _HardwareInput)]


class _Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("ii", _InputI)]


_INPUT_KEYBOARD = 1
_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004


def _utf16_units(text: str) -> List[int]:
    """Split ``text`` into UTF-16 code units (handles characters past the BMP)."""
    enc = text.encode("utf-16-le")
    return [enc[i] | (enc[i + 1] << 8) for i in range(0, len(enc), 2)]


def _send_unicode(text: str) -> None:
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]  # Windows-only
    extra = ctypes.c_ulong(0)
    for unit in _utf16_units(text):
        for flags in (_KEYEVENTF_UNICODE, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP):
            ki = _KeyBdInput(0, unit, flags, 0, ctypes.pointer(extra))
            inp = _Input(_INPUT_KEYBOARD, _InputI(ki=ki))
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


class WindowsInjector:
    def __init__(self, method: str = "auto"):
        self.method = method

    def available_methods(self) -> List[str]:
        return ["sendinput"]

    def inject_text(self, text: str) -> str:
        if not text:
            return "noop"
        _send_unicode(text)
        return "sendinput"


# --------------------------------------------------------------------------- #
# IPC: loopback TCP, with the port advertised via a small file
# --------------------------------------------------------------------------- #

_HOST = "127.0.0.1"


def _read_port(port_file: str) -> int:
    with open(port_file) as fh:
        return int(fh.read().strip())


class _TcpIpcServer:
    def __init__(self, handler: Callable[[str], str], port_file: str):
        self.handler = handler
        self.port_file = port_file
        self.path = port_file
        self._sock = None
        self._running = False

    def start(self) -> None:
        if os.path.exists(self.port_file):
            try:
                os.unlink(self.port_file)
            except OSError:
                pass
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((_HOST, 0))
        self._sock.listen(8)
        port = self._sock.getsockname()[1]
        os.makedirs(os.path.dirname(self.port_file), exist_ok=True)
        with open(self.port_file, "w") as fh:
            fh.write(str(port))
        self._running = True

    def serve_forever(self) -> None:
        assert self._sock is not None, "call start() first"
        while self._running:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                break
            with conn:
                try:
                    data = conn.recv(4096).decode("utf-8", "replace").strip()
                    if not data:
                        continue
                    try:
                        resp = self.handler(data)
                    except Exception as exc:  # noqa: BLE001
                        resp = f"error: {exc}"
                    conn.sendall((resp + "\n").encode())
                except OSError:
                    continue

    def stop(self) -> None:
        self._running = False
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if os.path.exists(self.port_file):
            try:
                os.unlink(self.port_file)
            except OSError:
                pass


# --------------------------------------------------------------------------- #
# Backend
# --------------------------------------------------------------------------- #

class WindowsBackend(Backend):
    name = "windows"

    def _port_file(self) -> str:
        return str(self.data_dir() / "ipc.port")

    # -- text injection ------------------------------------------------------

    def make_injector(self, method: str = "auto") -> Injector:
        return WindowsInjector(method=method)

    def injection_methods(self) -> List[str]:
        return ["sendinput"]

    # -- IPC -----------------------------------------------------------------

    def make_ipc_server(self, handler: Callable[[str], str]) -> IpcServer:
        return _TcpIpcServer(handler, self._port_file())

    def ipc_send(self, command: str, timeout: float = 5.0) -> str:
        port = _read_port(self._port_file())
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((_HOST, port))
            sock.sendall((command + "\n").encode())
            return sock.recv(65536).decode("utf-8", "replace").strip()

    def ipc_is_running(self, timeout: float = 1.0) -> bool:
        if not os.path.exists(self._port_file()):
            return False
        try:
            self.ipc_send("ping", timeout=timeout)
            return True
        except (OSError, ValueError):
            return False

    # -- notifications -------------------------------------------------------

    def notify(self, summary: str, body: str = "", enabled: bool = True) -> None:
        # Best-effort no-op for now; a toast implementation can slot in here.
        return

    # -- paths ---------------------------------------------------------------

    def config_dir(self) -> Path:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return Path(base) / "inkit-popos"

    def data_dir(self) -> Path:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(base) / "inkit-popos"

    # -- diagnostics ---------------------------------------------------------

    def doctor_extra(self) -> List[str]:
        return ["notifications: not implemented on Windows yet"]
