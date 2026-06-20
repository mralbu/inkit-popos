"""Linux / Wayland backend (Pop!_OS / COSMIC).

This is the original implementation, unchanged: it delegates to the existing
``inject`` (wtype/ydotool/clipboard), ``ipc`` (AF_UNIX socket) and ``notify``
(notify-send) modules, and resolves XDG paths exactly as before. Adding Windows
must not alter anything here.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable, List

from .. import inject as _inject
from .. import ipc as _ipc
from .. import notify as _notify
from .base import Backend, Injector, IpcServer


class LinuxBackend(Backend):
    name = "linux"

    # -- text injection ------------------------------------------------------

    def make_injector(self, method: str = "auto") -> Injector:
        return _inject.Injector(method=method)

    def injection_methods(self) -> List[str]:
        return _inject.available_methods()

    # -- IPC -----------------------------------------------------------------

    def make_ipc_server(self, handler: Callable[[str], str]) -> IpcServer:
        return _ipc.IpcServer(handler)

    def ipc_send(self, command: str, timeout: float = 5.0) -> str:
        return _ipc.send_command(command, timeout=timeout)

    def ipc_is_running(self, timeout: float = 1.0) -> bool:
        return _ipc.is_running()

    # -- notifications -------------------------------------------------------

    def notify(self, summary: str, body: str = "", enabled: bool = True) -> None:
        _notify.notify(summary, body, enabled=enabled)

    # -- paths ---------------------------------------------------------------

    def config_dir(self) -> Path:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        return Path(base) / "inkit-popos"

    def data_dir(self) -> Path:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        return Path(base) / "inkit-popos"

    # -- diagnostics ---------------------------------------------------------

    def doctor_extra(self) -> List[str]:
        return [
            "notify-send: "
            + ("installed" if shutil.which("notify-send") else "missing (notifications disabled)"),
            "ydotoold: "
            + ("running" if _ydotoold_ok() else "not detected (only needed for ydotool injection)"),
        ]


def _ydotoold_ok() -> bool:
    runtime = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    return os.path.exists(os.path.join(runtime, ".ydotool_socket")) or os.path.exists(
        "/run/ydotoold/socket"
    )
