"""Built-in formula registry and dynamic loading helpers."""

from __future__ import annotations

from importlib import import_module
from inspect import getmembers, isfunction
import pkgutil
from types import ModuleType
from typing import Iterable

from app.engine.formula_engine import FormulaEngine


def _discover_builtin_modules() -> list[str]:
    """Return modules under ``app.formulas`` prefixed with ``builtin_``."""
    package = import_module("app.formulas")
    return sorted(
        f"app.formulas.{module.name}"
        for module in pkgutil.iter_modules(package.__path__)
        if module.name.startswith("builtin_")
    )


def _iter_uppercase_functions(module: ModuleType) -> Iterable[tuple[str, object]]:
    for name, fn in getmembers(module, isfunction):
        if name.isupper():
            yield name, fn


def register_builtin_functions(engine: FormulaEngine) -> None:
    """Discover and register uppercase functions from builtin modules."""
    for module_path in _discover_builtin_modules():
        module = import_module(module_path)
        for name, fn in _iter_uppercase_functions(module):
            engine.register_function(name, fn)
            if "_" in name:
                engine.register_function(name.replace("_", "."), fn)
