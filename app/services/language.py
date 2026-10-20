"""Tiny, dependency-free language helpers."""

from __future__ import annotations

SUPPORTED_AUTO = {"en", "hi"}


def detect_language(text: str) -> str:
    """Return "hi" when the text is mostly Devanagari, otherwise "en".

    This is a script-based heuristic, not a full language identifier. For other
    languages the caller should pass the language code explicitly.
    """
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return "en"
    devanagari = sum(1 for ch in letters if "ऀ" <= ch <= "ॿ")
    return "hi" if devanagari / len(letters) >= 0.4 else "en"


def normalize_language_code(code: str | None) -> str:
    """Lower-case, strip region ("hi-IN" -> "hi"); empty or None means auto."""
    if not code:
        return "auto"
    code = code.strip().lower().replace("_", "-")
    if code in ("", "auto"):
        return "auto"
    return code.split("-")[0]
