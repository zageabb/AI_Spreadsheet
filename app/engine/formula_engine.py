"""Formula engine scaffold.

This module is intentionally lightweight for MVP and should be expanded to
support robust parsing, dependency graphs, and recalculation in later tasks.
"""

from __future__ import annotations

from typing import Any, Callable


class FormulaEngine:
    """Starter formula engine with limited built-in function support."""

    def __init__(self) -> None:
        self._functions: dict[str, Callable[..., Any]] = {}

    def register_function(self, name: str, fn: Callable[..., Any]) -> None:
        """Register a function name for formula execution."""
        self._functions[name.upper()] = fn

    def evaluate(self, raw_value: Any) -> Any:
        """Evaluate a raw value if it looks like a formula.

        Scaffold behavior:
        - Supports direct values as-is.
        - Supports formulas like '=SUM(1,2,3)' for registered functions.
        - Does not yet support cell references or expression grammar.
        """
        if not isinstance(raw_value, str) or not raw_value.startswith("="):
            return raw_value

        expression = raw_value[1:].strip()
        if "(" not in expression or not expression.endswith(")"):
            return raw_value

        fn_name, arg_str = expression[:-1].split("(", 1)
        fn = self._functions.get(fn_name.upper())
        if fn is None:
            return f"#NAME? ({fn_name})"

        args: list[Any] = []
        for token in [part.strip() for part in arg_str.split(",") if part.strip()]:
            try:
                args.append(float(token))
            except ValueError:
                args.append(token)

        try:
            return fn(*args)
        except Exception as exc:  # noqa: BLE001 - explicit scaffold fallback
            return f"#ERROR ({exc})"
