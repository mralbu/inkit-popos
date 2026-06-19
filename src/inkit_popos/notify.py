"""Best-effort desktop notifications via notify-send."""
from __future__ import annotations

import shutil
import subprocess

_APP_NAME = "InkIt"


def notify(summary: str, body: str = "", enabled: bool = True) -> None:
    if not enabled or not shutil.which("notify-send"):
        return
    try:
        subprocess.run(
            ["notify-send", "-a", _APP_NAME, "-i", "audio-input-microphone",
             summary, body],
            check=False,
        )
    except OSError:
        pass
