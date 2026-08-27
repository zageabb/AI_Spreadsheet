"""Validated authoring and registration of user Python spreadsheet functions."""

from __future__ import annotations

import ast
import math
import os
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.engine.formula_engine import FormulaEngine


_SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "enumerate": enumerate, "float": float, "int": int, "len": len,
    "list": list, "max": max, "min": min, "range": range, "round": round,
    "set": set, "sorted": sorted, "str": str, "sum": sum, "tuple": tuple,
    "zip": zip,
}
_FORBIDDEN_NAMES = {
    "breakpoint", "compile", "eval", "exec", "globals", "input", "locals",
    "open", "os", "pathlib", "socket", "subprocess", "sys", "__import__",
}
_MODULE_GLOBALS = {"math": math, "statistics": statistics}


class CustomFunctionError(ValueError):
    """Raised when custom function source is invalid or unsafe."""


@dataclass(frozen=True, slots=True)
class CustomFunctionResult:
    path: Path
    function_names: tuple[str, ...]


class CustomFunctionService:
    """Validate, persist, and immediately register local formula functions."""

    def __init__(self, functions_dir: str | Path | None = None) -> None:
        configured = functions_dir or os.getenv("CUSTOM_FUNCTIONS_DIR", "plugins/user")
        self.functions_dir = Path(configured).expanduser()

    def validate(self, source: str) -> tuple[str, ...]:
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise CustomFunctionError(f"Python syntax error on line {exc.lineno}: {exc.msg}") from exc
        functions = tuple(
            node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.isupper()
        )
        if not functions:
            raise CustomFunctionError("Define at least one uppercase function, for example DOUBLE(value).")
        declared_functions = {
            node.name for node in tree.body if isinstance(node, ast.FunctionDef)
        }
        allowed_calls = set(_SAFE_BUILTINS) | declared_functions
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                raise CustomFunctionError("Imports are disabled; math and statistics are already available.")
            if isinstance(node, (ast.Global, ast.Nonlocal, ast.AsyncFunctionDef, ast.Await, ast.Yield, ast.YieldFrom)):
                raise CustomFunctionError(f"{type(node).__name__} is not allowed in custom functions.")
            if isinstance(node, ast.Name) and (node.id in _FORBIDDEN_NAMES or node.id.startswith("__")):
                raise CustomFunctionError(f"Use of '{node.id}' is not allowed.")
            if isinstance(node, ast.Attribute):
                if node.attr.startswith("_") or not isinstance(node.value, ast.Name) or node.value.id not in _MODULE_GLOBALS:
                    raise CustomFunctionError("Only public math.* and statistics.* attributes are allowed.")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id not in allowed_calls:
                    raise CustomFunctionError(f"Calls to '{node.func.id}' are not allowed.")
        return functions

    def save_and_register(
        self, module_name: str, source: str, engine: FormulaEngine
    ) -> CustomFunctionResult:
        function_names = self.validate(source)
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", module_name.strip()).strip("_").lower()
        if not safe_name:
            raise CustomFunctionError("Provide a module name.")
        namespace: dict[str, Any] = {
            "__builtins__": _SAFE_BUILTINS, **_MODULE_GLOBALS,
        }
        try:
            exec(compile(source, f"<custom-function:{safe_name}>", "exec"), namespace)
        except Exception as exc:
            raise CustomFunctionError(f"Function module could not be loaded: {exc}") from exc
        for name in function_names:
            function = namespace.get(name)
            if not callable(function):
                raise CustomFunctionError(f"{name} did not compile to a callable function.")

        self.functions_dir.mkdir(parents=True, exist_ok=True)
        target = self.functions_dir / f"{safe_name}.py"
        temporary = target.with_suffix(".py.tmp")
        temporary.write_text(source.rstrip() + "\n", encoding="utf-8")
        temporary.replace(target)
        for name in function_names:
            engine.register_function(name, namespace[name])
        return CustomFunctionResult(target, function_names)

    def list_modules(self) -> list[Path]:
        if not self.functions_dir.exists():
            return []
        return sorted(path for path in self.functions_dir.glob("*.py") if not path.name.startswith("_"))
