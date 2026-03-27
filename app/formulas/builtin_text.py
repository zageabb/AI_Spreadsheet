"""Built-in Excel-style text functions for MVP."""

from __future__ import annotations

from typing import Any


def CONCAT(*parts: Any) -> str:  # noqa: N802
    return "".join("" if part is None else str(part) for part in parts)


def LEFT(text: Any, num_chars: Any = 1) -> str:  # noqa: N802
    source = "" if text is None else str(text)
    size = max(0, int(float(num_chars)))
    return source[:size]


def RIGHT(text: Any, num_chars: Any = 1) -> str:  # noqa: N802
    source = "" if text is None else str(text)
    size = max(0, int(float(num_chars)))
    if size == 0:
        return ""
    return source[-size:]


def LEN(text: Any) -> float:  # noqa: N802
    return float(len("" if text is None else str(text)))
