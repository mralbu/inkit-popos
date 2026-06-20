"""Configuration loading and defaults.

Config lives at ``$XDG_CONFIG_HOME/inkit-popos/config.toml`` (usually
``~/.config/inkit-popos/config.toml``). A first run can scaffold it with
``inkit-popos init``.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict

from .platform import get_backend

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on 3.9/3.10
    import tomli as tomllib  # type: ignore


DEFAULTS: Dict[str, Any] = {
    # Which STT engine to use: "cartesia" or "parakeet".
    "engine": "parakeet",
    "audio": {
        "sample_rate": 16000,
        "channels": 1,
        # PortAudio device name or index; null = system default input.
        "device": None,
    },
    "inject": {
        # "auto" | "wtype" | "ydotool" | "clipboard"
        "method": "auto",
    },
    "cartesia": {
        # Falls back to the CARTESIA_API_KEY environment variable.
        "api_key": None,
        "model": "ink-whisper",
        "language": "en",
    },
    "parakeet": {
        # Directory holding the sherpa-onnx Parakeet model files
        # (encoder*.onnx, decoder*.onnx, joiner*.onnx, tokens.txt).
        "model_dir": "~/.local/share/inkit-popos/models/parakeet",
        "num_threads": 2,
        "decoding_method": "greedy_search",
        "provider": "cpu",  # "cpu" or "cuda"
    },
    "polish": {
        # Optional LLM cleanup of the transcript (filler removal, punctuation).
        "enabled": False,
        # "openai" (OpenAI-compatible: OpenAI/Groq/local) or "anthropic".
        "provider": "openai",
        "model": "gpt-4o-mini",
        "api_key": None,  # falls back to provider env var
        "base_url": None,  # override for Groq/local OpenAI-compatible servers
    },
    "notify": True,
}


def config_dir() -> Path:
    return get_backend().config_dir()


def config_path() -> Path:
    return config_dir() / "config.toml"


def data_dir() -> Path:
    return get_backend().data_dir()


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config() -> Dict[str, Any]:
    """Return the effective config: defaults merged with the user's TOML."""
    cfg = copy.deepcopy(DEFAULTS)
    path = config_path()
    if path.exists():
        with open(path, "rb") as fh:
            user = tomllib.load(fh)
        _deep_merge(cfg, user)
    return cfg


DEFAULT_CONFIG_TEMPLATE = """# inkit-popos configuration
# See https://github.com/mralbu/inkit-popos for details.

# Engine: "parakeet" (local, offline) or "cartesia" (cloud API).
engine = "parakeet"

[audio]
sample_rate = 16000
channels = 1
# device = "alsa_input..."   # run `inkit-popos devices` to list inputs

[inject]
# How typed text reaches the focused window:
#   "auto"      try wtype, then ydotool, then clipboard paste
#   "wtype"     Wayland virtual-keyboard protocol (if your compositor supports it)
#   "ydotool"   kernel uinput (compositor-agnostic; needs ydotoold running)
#   "clipboard" copy + synthesize Ctrl+V
method = "auto"

[cartesia]
# Get a free key at https://cartesia.ai  (or set CARTESIA_API_KEY)
# api_key = "sk_car_..."
model = "ink-whisper"
language = "en"

[parakeet]
# Download a sherpa-onnx Parakeet model and point model_dir at it.
# See the README "Local Parakeet" section.
model_dir = "~/.local/share/inkit-popos/models/parakeet"
num_threads = 2
decoding_method = "greedy_search"
provider = "cpu"

[polish]
enabled = false
provider = "openai"        # "openai" (OpenAI-compatible) or "anthropic"
model = "gpt-4o-mini"
# api_key = "..."          # or set OPENAI_API_KEY / ANTHROPIC_API_KEY
# base_url = "https://api.groq.com/openai/v1"

# Desktop notifications via notify-send
notify = true
"""


def write_default_config(force: bool = False) -> Path:
    path = config_path()
    if path.exists() and not force:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_TEMPLATE)
    return path
