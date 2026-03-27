"""Extensible formula engine for parsing and evaluating spreadsheet formulas."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable, Iterable


CELL_REF_PATTERN = re.compile(r"^[A-Za-z]+[1-9][0-9]*$")


class FormulaEvaluationError(Exception):
    """Structured formula evaluation error with spreadsheet-style codes."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}{f' ({detail})' if detail else ''}")


@dataclass(slots=True)
class Token:
    """Token generated from a formula expression."""

    kind: str
    value: str


class FormulaEngine:
    """Formula engine with parser, evaluator, and function registry."""

    def __init__(self) -> None:
        self._functions: dict[str, Callable[..., Any]] = {}

    def register_function(self, name: str, fn: Callable[..., Any], *, override: bool = True) -> None:
        """Register a function for formula execution.

        Args:
            name: Function name; stored in case-insensitive (uppercase) form.
            fn: Callable implementation for the function.
            override: If ``False``, existing registrations are preserved.
        """
        if not callable(fn):
            raise TypeError(f"Function '{name}' is not callable.")

        normalized = name.strip().upper()
        if not normalized:
            raise ValueError("Function name must not be empty.")

        if not override and normalized in self._functions:
            return

        self._functions[normalized] = fn

    def has_function(self, name: str) -> bool:
        """Return whether a function is registered."""
        return name.strip().upper() in self._functions

    def list_functions(self) -> list[str]:
        """List registered function names."""
        return sorted(self._functions.keys())

    def evaluate(self, raw_value: Any, context: dict[str, Any] | None = None) -> Any:
        """Evaluate a value if it is a formula.

        Supported now:
        - Numeric and string literals
        - Same-sheet references (e.g., ``A1``)
        - Built-in and plugin function calls (e.g., ``SUM(A1, 2)``)
        - Basic operators: ``+ - * / ^`` and comparisons

        Future-ready scaffold:
        - Cross-sheet references are intentionally not yet implemented.
        """
        if not isinstance(raw_value, str) or not raw_value.startswith("="):
            return raw_value

        expression = raw_value[1:].strip()
        if not expression:
            return "#FORMULA!"

        try:
            parser = _Parser(tokens=_tokenize(expression), engine=self, context=context or {})
            return parser.parse()
        except FormulaEvaluationError as exc:
            return exc.code
        except Exception:
            return "#ERROR!"


class _Parser:
    """Recursive-descent parser for spreadsheet formula expressions."""

    def __init__(self, tokens: list[Token], engine: FormulaEngine, context: dict[str, Any]) -> None:
        self.tokens = tokens + [Token("EOF", "")]
        self.engine = engine
        self.context = context
        self.index = 0

    def parse(self) -> Any:
        result = self._parse_comparison()
        if self._peek().kind != "EOF":
            raise FormulaEvaluationError("#PARSE!", "Unexpected trailing tokens")
        return result

    def _parse_comparison(self) -> Any:
        left = self._parse_add_sub()
        while self._peek().kind in {"EQ", "NE", "LT", "LE", "GT", "GE"}:
            op = self._consume().kind
            right = self._parse_add_sub()
            left = self._apply_comparison(op, left, right)
        return left

    def _parse_add_sub(self) -> Any:
        left = self._parse_mul_div_pow()
        while self._peek().kind in {"PLUS", "MINUS"}:
            op = self._consume().kind
            right = self._parse_mul_div_pow()
            left = self._apply_arithmetic(op, left, right)
        return left

    def _parse_mul_div_pow(self) -> Any:
        left = self._parse_unary()
        while self._peek().kind in {"STAR", "SLASH", "CARET"}:
            op = self._consume().kind
            right = self._parse_unary()
            left = self._apply_arithmetic(op, left, right)
        return left

    def _parse_unary(self) -> Any:
        if self._peek().kind == "PLUS":
            self._consume("PLUS")
            return self._coerce_number(self._parse_unary())
        if self._peek().kind == "MINUS":
            self._consume("MINUS")
            return -self._coerce_number(self._parse_unary())
        return self._parse_primary()

    def _parse_primary(self) -> Any:
        token = self._peek()

        if token.kind == "NUMBER":
            self._consume("NUMBER")
            return float(token.value)

        if token.kind == "STRING":
            self._consume("STRING")
            return token.value

        if token.kind == "LPAREN":
            self._consume("LPAREN")
            value = self._parse_comparison()
            self._consume("RPAREN")
            return value

        if token.kind == "IDENT":
            ident = self._consume("IDENT").value
            if self._peek().kind == "LPAREN":
                return self._parse_function_call(ident)
            if ident.upper() in {"TRUE", "FALSE"}:
                return ident.upper() == "TRUE"
            if CELL_REF_PATTERN.match(ident):
                return self._resolve_reference(ident.upper())
            raise FormulaEvaluationError("#NAME?", ident)

        raise FormulaEvaluationError("#PARSE!", f"Unexpected token: {token.kind}")

    def _parse_function_call(self, fn_name: str) -> Any:
        self._consume("LPAREN")
        args: list[Any] = []

        if self._peek().kind != "RPAREN":
            while True:
                args.append(self._parse_comparison())
                if self._peek().kind != "COMMA":
                    break
                self._consume("COMMA")

        self._consume("RPAREN")

        fn = self.engine._functions.get(fn_name.upper())
        if fn is None:
            raise FormulaEvaluationError("#NAME?", fn_name)

        try:
            return fn(*args)
        except FormulaEvaluationError:
            raise
        except Exception as exc:
            raise FormulaEvaluationError("#VALUE!", str(exc)) from exc

    def _resolve_reference(self, reference: str) -> Any:
        if "!" in reference:
            raise FormulaEvaluationError("#REF!", "Cross-sheet references not implemented yet")

        resolver = self.context.get("get_cell_value")
        if resolver is None:
            raise FormulaEvaluationError("#REF!", f"No resolver for {reference}")

        try:
            resolved = resolver(reference)
        except FormulaEvaluationError:
            raise
        except Exception as exc:
            raise FormulaEvaluationError("#REF!", str(exc)) from exc

        if isinstance(resolved, str) and resolved.startswith("#"):
            raise FormulaEvaluationError(resolved)
        return resolved

    @staticmethod
    def _coerce_number(value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == "":
                return 0.0
            try:
                return float(stripped)
            except ValueError as exc:
                raise FormulaEvaluationError("#VALUE!", f"Cannot coerce '{value}' to number") from exc
        raise FormulaEvaluationError("#VALUE!", f"Unsupported numeric value: {type(value).__name__}")

    def _apply_arithmetic(self, op: str, left: Any, right: Any) -> float:
        lhs = self._coerce_number(left)
        rhs = self._coerce_number(right)

        if op == "PLUS":
            return lhs + rhs
        if op == "MINUS":
            return lhs - rhs
        if op == "STAR":
            return lhs * rhs
        if op == "SLASH":
            if rhs == 0:
                raise FormulaEvaluationError("#DIV/0!")
            return lhs / rhs
        if op == "CARET":
            return lhs**rhs
        raise FormulaEvaluationError("#ERROR!", f"Unknown operator {op}")

    @staticmethod
    def _apply_comparison(op: str, left: Any, right: Any) -> bool:
        if op == "EQ":
            return left == right
        if op == "NE":
            return left != right
        if op == "LT":
            return left < right
        if op == "LE":
            return left <= right
        if op == "GT":
            return left > right
        if op == "GE":
            return left >= right
        raise FormulaEvaluationError("#ERROR!", f"Unknown comparison operator {op}")

    def _peek(self) -> Token:
        return self.tokens[self.index]

    def _consume(self, expected: str | None = None) -> Token:
        token = self.tokens[self.index]
        if expected is not None and token.kind != expected:
            raise FormulaEvaluationError("#PARSE!", f"Expected {expected}, got {token.kind}")
        self.index += 1
        return token


def _tokenize(expression: str) -> list[Token]:
    """Tokenize a formula expression into parser tokens."""
    token_specs: list[tuple[str, str]] = [
        ("SPACE", r"[ \t\r\n]+"),
        ("NUMBER", r"\d+(?:\.\d+)?"),
        ("STRING", r'"([^"\\]|\\.)*"'),
        ("LE", r"<="),
        ("GE", r">="),
        ("NE", r"<>|!="),
        ("EQ", r"="),
        ("LT", r"<"),
        ("GT", r">"),
        ("PLUS", r"\+"),
        ("MINUS", r"-"),
        ("STAR", r"\*"),
        ("SLASH", r"/"),
        ("CARET", r"\^"),
        ("COMMA", r","),
        ("LPAREN", r"\("),
        ("RPAREN", r"\)"),
        ("IDENT", r"[A-Za-z_][A-Za-z0-9_]*"),
    ]

    pattern = "|".join(f"(?P<{name}>{regex})" for name, regex in token_specs)
    tokens: list[Token] = []

    for match in re.finditer(pattern, expression):
        kind = match.lastgroup
        value = match.group()
        if kind == "SPACE":
            continue
        if kind == "STRING":
            value = _unescape_string(value)
        tokens.append(Token(kind=kind or "", value=value))

    consumed = "".join(m.group() for m in re.finditer(pattern, expression))
    if consumed != expression:
        raise FormulaEvaluationError("#PARSE!", "Invalid token in expression")

    return tokens


def _unescape_string(quoted: str) -> str:
    """Convert a quoted token into its unescaped string value."""
    core = quoted[1:-1]
    return bytes(core, "utf-8").decode("unicode_escape")


def flatten_args(args: Iterable[Any]) -> list[Any]:
    """Flatten nested iterables for function implementations."""
    flattened: list[Any] = []
    for arg in args:
        if isinstance(arg, (list, tuple)):
            flattened.extend(flatten_args(arg))
        else:
            flattened.append(arg)
    return flattened
