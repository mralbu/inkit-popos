"""Platform-backend tests.

The headline guarantee of the platform refactor: the Linux / Wayland path is
unchanged. These tests pin that down (the Linux backend still delegates to the
original ``inject``/``ipc``/``notify`` modules and the original XDG paths), and
separately exercise the Windows toggle path (loopback-TCP IPC), which is
testable on any OS.
"""
from __future__ import annotations

import os
import threading
import time

import pytest

from inkit_popos import config, inject, ipc
from inkit_popos.platform import get_backend
from inkit_popos.platform.linux import LinuxBackend


# --------------------------------------------------------------------------- #
# Linux: provably unchanged
# --------------------------------------------------------------------------- #

def test_default_backend_is_linux_off_windows():
    # In CI / dev this runs on Linux; get_backend() must pick LinuxBackend.
    assert isinstance(get_backend(), LinuxBackend)


def test_linux_injector_is_the_original_class():
    backend = LinuxBackend()
    assert isinstance(backend.make_injector("auto"), inject.Injector)
    assert backend.injection_methods() == inject.available_methods()


def test_linux_ipc_server_is_the_original_class():
    backend = LinuxBackend()
    server = backend.make_ipc_server(lambda cmd: "pong")
    assert isinstance(server, ipc.IpcServer)
    assert server.path == ipc.socket_path()


def test_linux_paths_match_xdg(monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/cfg")
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/data")
    backend = LinuxBackend()
    assert str(backend.config_dir()) == "/tmp/cfg/inkit-popos"
    assert str(backend.data_dir()) == "/tmp/data/inkit-popos"
    # config.py routes through the backend, so it agrees.
    assert config.config_path() == backend.config_dir() / "config.toml"


# --------------------------------------------------------------------------- #
# Windows: toggle path (importable + IPC works everywhere)
# --------------------------------------------------------------------------- #

def test_windows_injector_reports_sendinput():
    from inkit_popos.platform.windows import WindowsInjector, _utf16_units

    inj = WindowsInjector("auto")
    assert inj.available_methods() == ["sendinput"]
    # UTF-16 splitting handles characters beyond the BMP (surrogate pairs).
    assert _utf16_units("hi") == [ord("h"), ord("i")]
    assert len(_utf16_units("😀")) == 2


def test_windows_ipc_toggle_roundtrip(tmp_path):
    from inkit_popos.platform.windows import WindowsBackend

    backend = WindowsBackend()
    port_file = str(tmp_path / "ipc.port")
    backend._port_file = lambda: port_file  # type: ignore[method-assign]

    assert backend.ipc_is_running(timeout=0.5) is False

    seen = []

    def handler(cmd: str) -> str:
        seen.append(cmd)
        return "pong" if cmd == "ping" else f"ok:{cmd}"

    server = backend.make_ipc_server(handler)
    server.start()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        time.sleep(0.05)
        assert backend.ipc_is_running(timeout=0.5) is True
        assert backend.ipc_send("toggle") == "ok:toggle"
    finally:
        server.stop()
        thread.join(timeout=1.0)

    assert "toggle" in seen
    assert not os.path.exists(port_file)  # cleaned up on stop
