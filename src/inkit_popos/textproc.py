"""Deterministic post-processing of transcripts (no network, stdlib only).

Two independent, config-driven passes:

* **Spoken punctuation** — turn dictated words into symbols, the way classic
  dictation tools do: ``"hello comma world period"`` -> ``"Hello, world."`` and
  ``"item one new line item two"`` -> two lines.
* **Word replacements** — a per-user substitution table applied last, so it has
  the final say over both the raw transcript and any LLM ``polish``:
  ``"pop os"`` -> ``"Pop!_OS"``.

Both run before/around the optional LLM polish; see ``daemon._process``.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Mapping

# Spoken phrase -> the symbol it becomes. Multi-word phrases are matched before
# their shorter overlaps (we sort by length), so "exclamation mark" wins over a
# hypothetical "mark". Kept intentionally conservative: high-confidence phrases
# only. Users add their own via [punctuation.extra].
DEFAULT_PUNCTUATION: Dict[str, str] = {
    "comma": ",",
    "period": ".",
    "full stop": ".",
    "question mark": "?",
    "exclamation mark": "!",
    "exclamation point": "!",
    "colon": ":",
    "semicolon": ";",
    "ellipsis": "…",
    "open paren": "(",
    "open parenthesis": "(",
    "close paren": ")",
    "close parenthesis": ")",
    "open bracket": "[",
    "close bracket": "]",
    "new paragraph": "\n\n",
    "new line": "\n",
    "newline": "\n",
}

# Symbols that hug the preceding word (drop the space before them).
_HUG_LEFT = ",.;:!?…)]"
# Symbols that hug the following word (drop the space after them).
_HUG_RIGHT = "(["


def apply_spoken_punctuation(text: str, config: Mapping[str, Any]) -> str:
    """Replace spoken punctuation words with symbols, then tidy spacing.

    Controlled by ``config`` (the ``[punctuation]`` table):
    ``enabled`` (default True), ``capitalize`` (default True) and an optional
    ``extra`` mapping that adds to / overrides the defaults.
    """
    if not text or not config.get("enabled", True):
        return text

    mapping: Dict[str, str] = dict(DEFAULT_PUNCTUATION)
    extra = config.get("extra")
    if isinstance(extra, Mapping):
        mapping.update({str(k).lower(): str(v) for k, v in extra.items()})

    # Longest phrases first so "exclamation mark" matches before "mark".
    phrases = sorted(mapping, key=len, reverse=True)
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(p) for p in phrases) + r")\b",
        re.IGNORECASE,
    )
    text = pattern.sub(lambda m: mapping[m.group(1).lower()], text)
    text = _normalize_spacing(text)
    if config.get("capitalize", True):
        text = _capitalize_sentences(text)
    return text


def apply_replacements(text: str, config: Mapping[str, Any]) -> str:
    """Apply the user's word/phrase substitution table (the ``[replacements]``).

    ``enabled`` (default True), ``case_sensitive`` (default False) and ``map``,
    a phrase -> replacement table. Matching is whole-word (``\\b`` bounded);
    replacements are emitted verbatim so their own casing is preserved.
    """
    if not text or not config.get("enabled", True):
        return text
    mapping = config.get("map")
    if not isinstance(mapping, Mapping) or not mapping:
        return text

    flags = 0 if config.get("case_sensitive") else re.IGNORECASE
    # Longest source phrases first so multi-word entries win over their parts.
    for phrase in sorted((str(k) for k in mapping), key=len, reverse=True):
        repl = str(mapping[phrase])
        pattern = re.compile(r"\b" + re.escape(phrase) + r"\b", flags)
        # Use a function so backslashes/group refs in `repl` stay literal.
        text = pattern.sub(lambda _m, r=repl: r, text)
    return text


def _normalize_spacing(text: str) -> str:
    text = re.sub(r"[ \t]+([" + re.escape(_HUG_LEFT) + r"])", r"\1", text)
    text = re.sub(r"([" + re.escape(_HUG_RIGHT) + r"])[ \t]+", r"\1", text)
    # Collapse whitespace around newlines, then runs of spaces/tabs.
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    # No more than two consecutive newlines (paragraph break).
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_SENTENCE_START = re.compile(r"(^|[.!?]\s+|\n\s*)([a-z])")


def _capitalize_sentences(text: str) -> str:
    return _SENTENCE_START.sub(lambda m: m.group(1) + m.group(2).upper(), text)
