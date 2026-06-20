"""Platform backends.

Everything that differs between operating systems — text injection, the
daemon/CLI IPC transport, desktop notifications and config/data paths — lives
behind a :class:`~inkit_popos.platform.base.Backend`. The rest of the codebase
talks to the backend, never to ``sys.platform`` directly.

``get_backend()`` is the single place the platform is chosen. Linux (and any
other POSIX target we don't special-case) gets the original Pop!_OS / Wayland
implementation unchanged; Windows gets its own backend.
"""
from __future__ import annotations

import sys
from functools import lru_cache

from .base import Backend

__all__ = ["Backend", "get_backend"]


@lru_cache(maxsize=1)
def get_backend() -> Backend:
    """Return the cached backend for the current OS."""
    if sys.platform.startswith("win"):
        from .windows import WindowsBackend

        return WindowsBackend()
    # Linux and every other (POSIX) platform use the original implementation.
    from .linux import LinuxBackend

    return LinuxBackend()
