"""Type text into the focused window on Wayland.

Wayland blocks arbitrary synthetic input, so there is no single portable way to
do this. We try, in order:

1. ``wtype``  - virtual-keyboard protocol (zwp_virtual_keyboard_v1). Clean, but
   only works if the compositor advertises the protocol.
2. ``ydotool`` - kernel uinput; compositor-agnostic but needs ``ydotoold``
   running and access to ``/dev/uinput``.
3. clipboard - copy with ``wl-copy`` then synthesize Ctrl+V.
"""
from __future__ import annotations

import shutil
import subprocess

# Linux input event codes for the clipboard-paste fallback.
_KEY_LEFTCTRL = 29
_KEY_V = 47


class InjectionError(RuntimeError):
    pass


def available_methods() -> list[str]:
    methods = []
    if shutil.which("wtype"):
        methods.append("wtype")
    if shutil.which("ydotool"):
        methods.append("ydotool")
    if shutil.which("wl-copy"):
        methods.append("clipboard")
    return methods


class Injector:
    def __init__(self, method: str = "auto"):
        self.method = method

    def _chain(self) -> list[str]:
        if self.method and self.method != "auto":
            return [self.method]
        # Preferred order for auto mode.
        order = ["wtype", "ydotool", "clipboard"]
        avail = set(available_methods())
        return [m for m in order if m in avail]

    def inject_text(self, text: str) -> str:
        """Type ``text``. Returns the method that succeeded."""
        if not text:
            return "noop"
        chain = self._chain()
        if not chain:
            raise InjectionError(
                "No text-injection tool found. Install one of: wtype, ydotool, "
                "or wl-clipboard (wl-copy)."
            )
        last_err = None
        for method in chain:
            try:
                getattr(self, f"_via_{method}")(text)
                return method
            except Exception as exc:  # noqa: BLE001 - fall through to next method
                last_err = exc
        raise InjectionError(f"All injection methods failed ({chain}): {last_err}")

    # -- individual backends -------------------------------------------------

    def _via_wtype(self, text: str) -> None:
        subprocess.run(["wtype", text], check=True)

    def _via_ydotool(self, text: str) -> None:
        subprocess.run(["ydotool", "type", "--", text], check=True)

    def _via_clipboard(self, text: str) -> None:
        subprocess.run(["wl-copy"], input=text.encode(), check=True)
        # Synthesize Ctrl+V with whatever key tool is available.
        if shutil.which("wtype"):
            subprocess.run(
                ["wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl"], check=True
            )
        elif shutil.which("ydotool"):
            subprocess.run(
                [
                    "ydotool",
                    "key",
                    f"{_KEY_LEFTCTRL}:1",
                    f"{_KEY_V}:1",
                    f"{_KEY_V}:0",
                    f"{_KEY_LEFTCTRL}:0",
                ],
                check=True,
            )
        # else: text is on the clipboard; the user can paste manually.
