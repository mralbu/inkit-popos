"""STT engine implementations and a factory."""
from __future__ import annotations

from typing import Any, Dict

from .base import SttEngine


def build_engine(config: Dict[str, Any]) -> SttEngine:
    """Construct the STT engine selected by ``config['engine']``."""
    name = (config.get("engine") or "parakeet").lower()
    if name == "cartesia":
        from .cartesia import CartesiaEngine

        c = config.get("cartesia", {})
        return CartesiaEngine(
            api_key=c.get("api_key"),
            model=c.get("model", "ink-whisper"),
            language=c.get("language", "en"),
        )
    if name == "parakeet":
        from .parakeet import ParakeetEngine

        p = config.get("parakeet", {})
        return ParakeetEngine(
            model_dir=p.get("model_dir"),
            num_threads=p.get("num_threads", 2),
            decoding_method=p.get("decoding_method", "greedy_search"),
            provider=p.get("provider", "cpu"),
        )
    raise ValueError(f"Unknown engine: {name!r} (expected 'cartesia' or 'parakeet')")
