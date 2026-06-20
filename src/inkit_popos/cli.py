"""Command-line entry point.

Typical use:
    inkit-popos init          # write a starter config
    inkit-popos doctor        # check audio / injection / engine setup
    inkit-popos daemon        # run the background service
    inkit-popos toggle        # bind this to a COSMIC keyboard shortcut
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from . import ipc
from .config import config_path, load_config, write_default_config


def _cmd_init(args: argparse.Namespace) -> int:
    path = write_default_config(force=args.force)
    print(f"Config at {path}")
    if not args.force:
        print("(use --force to overwrite an existing file)")
    return 0


def _cmd_daemon(args: argparse.Namespace) -> int:
    from .daemon import Daemon

    if ipc.is_running():
        print("A daemon is already running on this socket.", file=sys.stderr)
        return 1
    config = load_config()
    return Daemon(config).run()


def _send(command: str) -> int:
    if not ipc.is_running():
        print("Daemon is not running. Start it with: inkit-popos daemon", file=sys.stderr)
        return 1
    try:
        print(ipc.send_command(command))
        return 0
    except OSError as exc:
        print(f"IPC error: {exc}", file=sys.stderr)
        return 1


def _cmd_toggle(args: argparse.Namespace) -> int:
    return _send("toggle")


def _cmd_start(args: argparse.Namespace) -> int:
    return _send("start")


def _cmd_stop(args: argparse.Namespace) -> int:
    return _send("stop")


def _cmd_cancel(args: argparse.Namespace) -> int:
    return _send("cancel")


def _cmd_status(args: argparse.Namespace) -> int:
    return _send("status")


def _cmd_quit(args: argparse.Namespace) -> int:
    return _send("quit")


def _cmd_devices(args: argparse.Namespace) -> int:
    from .audio import list_input_devices

    for dev in list_input_devices():
        print(f"  [{dev['index']}] {dev['name']}")
    return 0


def _cmd_transcribe(args: argparse.Namespace) -> int:
    """Transcribe an audio file directly (no daemon) for testing engines."""
    from .audio import load_audio
    from .engines import build_engine

    config = load_config()
    engine = build_engine(config)
    audio = load_audio(args.file, target_rate=config.get("audio", {}).get("sample_rate", 16000))
    text = engine.transcribe(audio, config.get("audio", {}).get("sample_rate", 16000))
    print(text)
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    import shutil

    from .inject import available_methods

    config = load_config()
    ok = True

    print(f"inkit-popos {__version__}")
    print(f"config: {config_path()} ({'exists' if config_path().exists() else 'missing — run: inkit-popos init'})")
    print(f"engine: {config.get('engine')}")

    # Audio
    try:
        from .audio import list_input_devices

        devices = list_input_devices()
        print(f"audio input devices: {len(devices)} found" if devices else "audio: NO input devices found")
        ok = ok and bool(devices)
    except Exception as exc:  # noqa: BLE001
        print(f"audio: ERROR ({exc}) — is sounddevice/PortAudio installed?")
        ok = False

    # Injection
    methods = available_methods()
    print(f"injection tools: {', '.join(methods) if methods else 'NONE — install wtype, ydotool, or wl-clipboard'}")
    ok = ok and bool(methods)

    # Engine availability
    engine_name = (config.get("engine") or "").lower()
    if engine_name == "cartesia":
        try:
            import cartesia  # noqa: F401

            print("cartesia SDK: installed")
        except ImportError:
            print("cartesia SDK: MISSING — pip install 'inkit-popos[cartesia]'")
            ok = False
    elif engine_name == "parakeet":
        try:
            import sherpa_onnx  # noqa: F401

            print("sherpa-onnx: installed")
        except ImportError:
            print("sherpa-onnx: MISSING — pip install 'inkit-popos[parakeet]'")
            ok = False
        import os

        model_dir = os.path.expanduser(config.get("parakeet", {}).get("model_dir", ""))
        print(f"parakeet model_dir: {model_dir} ({'found' if os.path.isdir(model_dir) else 'MISSING — see README'})")
        ok = ok and os.path.isdir(model_dir)

    if config.get("punctuation", {}).get("enabled", True):
        print("spoken punctuation: enabled")
    repl = config.get("replacements", {})
    if repl.get("enabled", True) and repl.get("map"):
        print(f"word replacements: {len(repl['map'])} rule(s)")
    if config.get("polish", {}).get("enabled"):
        print("polish: enabled")

    print("notify-send:", "installed" if shutil.which("notify-send") else "missing (notifications disabled)")
    print("ydotoold:", "running" if _ydotoold_ok() else "not detected (only needed for ydotool injection)")

    print("\nstatus:", "OK" if ok else "issues found — see above")
    return 0 if ok else 1


def _ydotoold_ok() -> bool:
    import os

    runtime = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    return os.path.exists(os.path.join(runtime, ".ydotool_socket")) or os.path.exists(
        "/run/ydotoold/socket"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="inkit-popos", description=__doc__)
    parser.add_argument("--version", action="version", version=f"inkit-popos {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="write a starter config file")
    p_init.add_argument("--force", action="store_true", help="overwrite existing config")
    p_init.set_defaults(func=_cmd_init)

    sub.add_parser("doctor", help="check audio/injection/engine setup").set_defaults(func=_cmd_doctor)
    sub.add_parser("daemon", help="run the background dictation service").set_defaults(func=_cmd_daemon)
    sub.add_parser("toggle", help="start/stop dictation (bind to a hotkey)").set_defaults(func=_cmd_toggle)
    sub.add_parser("start", help="begin recording").set_defaults(func=_cmd_start)
    sub.add_parser("stop", help="stop recording and transcribe").set_defaults(func=_cmd_stop)
    sub.add_parser("cancel", help="discard the current recording (bind to a hotkey)").set_defaults(func=_cmd_cancel)
    sub.add_parser("status", help="show daemon state").set_defaults(func=_cmd_status)
    sub.add_parser("quit", help="stop the daemon").set_defaults(func=_cmd_quit)
    sub.add_parser("devices", help="list audio input devices").set_defaults(func=_cmd_devices)

    p_tr = sub.add_parser("transcribe", help="transcribe an audio file (testing)")
    p_tr.add_argument("file", help="path to an audio file (wav/mp3/flac/ogg/…)")
    p_tr.set_defaults(func=_cmd_transcribe)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
