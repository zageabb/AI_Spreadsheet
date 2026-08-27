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


def MID(text: Any, start_num: Any, num_chars: Any) -> str:  # noqa: N802
    source = "" if text is None else str(text)
    start = max(0, int(float(start_num)) - 1)
    size = max(0, int(float(num_chars)))
    return source[start:start + size]


def TRIM(text: Any) -> str:  # noqa: N802
    return " ".join(("" if text is None else str(text)).split())


def UPPER(text: Any) -> str:  # noqa: N802
    return ("" if text is None else str(text)).upper()


def LOWER(text: Any) -> str:  # noqa: N802
    return ("" if text is None else str(text)).lower()


def SUBSTITUTE(text: Any, old_text: Any, new_text: Any, instance_num: Any = None) -> str:  # noqa: N802
    source, old, new = str(text), str(old_text), str(new_text)
    if instance_num is None:
        return source.replace(old, new)
    wanted = int(float(instance_num))
    if wanted < 1:
        raise ValueError("#VALUE!")
    parts = source.split(old)
    if wanted >= len(parts):
        return source
    return old.join(parts[:wanted]) + new + old.join(parts[wanted:])


def TEXTJOIN(delimiter: Any, ignore_empty: Any, *parts: Any) -> str:  # noqa: N802
    from app.engine.formula_engine import flatten_args
    values = flatten_args(parts)
    if bool(ignore_empty):
        values = [value for value in values if value not in (None, "")]
    return str(delimiter).join("" if value is None else str(value) for value in values)


def FIND(find_text: Any, within_text: Any, start_num: Any = 1) -> float:  # noqa: N802
    start=max(0,int(float(start_num))-1)
    position=str(within_text).find(str(find_text),start)
    if position<0:raise ValueError("#VALUE!")
    return float(position+1)


def SEARCH(find_text: Any, within_text: Any, start_num: Any = 1) -> float:  # noqa: N802
    return FIND(str(find_text).casefold(),str(within_text).casefold(),start_num)


def REPLACE(old_text: Any, start_num: Any, num_chars: Any, new_text: Any) -> str:  # noqa: N802
    source=str(old_text); start=max(0,int(float(start_num))-1); size=max(0,int(float(num_chars)))
    return source[:start]+str(new_text)+source[start+size:]


def VALUE(text: Any) -> float:  # noqa: N802
    return float(str(text).replace(",","").strip())
