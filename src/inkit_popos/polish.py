"""Optional LLM 'polish' of transcripts.

Mirrors InkIt's Polish feature: remove filler words and fix punctuation/casing
*without* rewriting the content. Implemented with the standard library so it
needs no extra dependencies. Supports OpenAI-compatible chat APIs (OpenAI,
Groq, local servers) and the Anthropic Messages API.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict

SYSTEM_PROMPT = (
    "You clean up dictated speech. Remove filler words (um, uh, like), fix "
    "punctuation, capitalization and obvious transcription slips. Do NOT "
    "rewrite, summarize, translate, or add content. Preserve the speaker's "
    "wording and meaning. Reply with only the cleaned text."
)


def polish_text(text: str, config: Dict[str, Any]) -> str:
    text = (text or "").strip()
    if not text:
        return text
    provider = (config.get("provider") or "openai").lower()
    if provider == "anthropic":
        return _polish_anthropic(text, config)
    return _polish_openai(text, config)


def _http_post_json(url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _polish_openai(text: str, config: Dict[str, Any]) -> str:
    api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY") or os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("polish: no API key (set polish.api_key or OPENAI_API_KEY)")
    base_url = (config.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    body = _http_post_json(
        f"{base_url}/chat/completions",
        {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        {
            "model": config.get("model", "gpt-4o-mini"),
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        },
    )
    return body["choices"][0]["message"]["content"].strip()


def _polish_anthropic(text: str, config: Dict[str, Any]) -> str:
    api_key = config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("polish: no API key (set polish.api_key or ANTHROPIC_API_KEY)")
    base_url = (config.get("base_url") or "https://api.anthropic.com").rstrip("/")
    body = _http_post_json(
        f"{base_url}/v1/messages",
        {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        {
            "model": config.get("model", "claude-haiku-4-5"),
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": text}],
        },
    )
    return "".join(
        block.get("text", "") for block in body.get("content", [])
    ).strip()
