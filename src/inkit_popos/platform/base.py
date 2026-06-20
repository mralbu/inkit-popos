"""Interfaces every platform backend implements.

The daemon and CLI depend only on these shapes, so adding an OS means adding a
``Backend`` subclass — not editing the shared pipeline (record → STT → polish →
inject) or the existing Linux code paths.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, List, Protocol, runtime_checkable


@runtime_checkable
class Injector(Protocol):
    """Types text into whatever window currently has focus."""

    def available_methods(self) -> List[str]:
        """Injection methods usable right now, best first."""

    def inject_text(self, text: str) -> str:
        """Type ``text``; return the method that succeeded (or ``"noop"``)."""


@runtime_checkable
class IpcServer(Protocol):
    """A listening endpoint the CLI connects to, one command per connection."""

    path: str

    def start(self) -> None: ...

    def serve_forever(self) -> None: ...

    def stop(self) -> None: ...


class Backend(ABC):
    """Per-OS implementation of the platform-specific seams."""

    name: str = "base"

    # -- text injection ------------------------------------------------------

    @abstractmethod
    def make_injector(self, method: str = "auto") -> Injector:
        """Build the injector, honouring the ``[inject] method`` config."""

    @abstractmethod
    def injection_methods(self) -> List[str]:
        """Injection methods available on this machine (for ``doctor``)."""

    # -- IPC (daemon side + client side) -------------------------------------

    @abstractmethod
    def make_ipc_server(self, handler: Callable[[str], str]) -> IpcServer:
        """Create the listening server the daemon serves commands on."""

    @abstractmethod
    def ipc_send(self, command: str, timeout: float = 5.0) -> str:
        """Send a single command to a running daemon and return its reply."""

    @abstractmethod
    def ipc_is_running(self, timeout: float = 1.0) -> bool:
        """True if a daemon is reachable on this machine's IPC endpoint."""

    # -- notifications -------------------------------------------------------

    @abstractmethod
    def notify(self, summary: str, body: str = "", enabled: bool = True) -> None:
        """Show a best-effort desktop notification."""

    # -- paths ---------------------------------------------------------------

    @abstractmethod
    def config_dir(self) -> Path:
        """Directory holding ``config.toml``."""

    @abstractmethod
    def data_dir(self) -> Path:
        """Directory for downloaded models and other app data."""

    # -- diagnostics ---------------------------------------------------------

    def doctor_extra(self) -> List[str]:
        """Extra platform-specific lines for ``inkit-popos doctor``."""
        return []
