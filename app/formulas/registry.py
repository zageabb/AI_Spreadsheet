"""Built-in formula registry and dynamic loading helpers."""

from __future__ import annotations

from importlib import import_module
from inspect import getmembers, isfunction

from app.engine.formula_engine import FormulaEngine


BUILTIN_MODULES = [
    "app.formulas.builtin_math",
]


def register_builtin_functions(engine: FormulaEngine) -> None:
    """Discover and register uppercase functions from builtin modules."""
    for module_path in BUILTIN_MODULES:
        module = import_module(module_path)
        for name, fn in getmembers(module, isfunction):
            if name.isupper():
                engine.register_function(name, fn)
