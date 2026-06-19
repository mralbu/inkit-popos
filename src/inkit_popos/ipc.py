"""Tiny line-based IPC over a Unix domain socket.

The daemon listens; the CLI (`toggle`, `start`, `stop`, `status`, bound to a
COSMIC keyboard shortcut) connects and sends a single command line.
"""
from __future__ import annotations

import os
import socket
from typing import Callable, Optional


def socket_path() -> str:
    runtime = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    return os.path.join(runtime, "inkit-popos.sock")


class IpcServer:
    def __init__(self, handler: Callable[[str], str], path: Optional[str] = None):
        self.path = path or socket_path()
        self.handler = handler
        self._sock: Optional[socket.socket] = None
        self._running = False

    def start(self) -> None:
        if os.path.exists(self.path):
            os.unlink(self.path)
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(self.path)
        self._sock.listen(8)
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
        if os.path.exists(self.path):
            try:
                os.unlink(self.path)
            except OSError:
                pass


def is_running(path: Optional[str] = None) -> bool:
    path = path or socket_path()
    if not os.path.exists(path):
        return False
    try:
        send_command("ping", path=path, timeout=1.0)
        return True
    except OSError:
        return False


def send_command(command: str, path: Optional[str] = None, timeout: float = 5.0) -> str:
    path = path or socket_path()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(path)
        sock.sendall((command + "\n").encode())
        return sock.recv(65536).decode("utf-8", "replace").strip()
