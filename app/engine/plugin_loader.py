"""Plugin formula loader scaffold."""

from __future__ import annotations

from importlib import import_module
from inspect import getmembers, isfunction
from pathlib import Path

from app.engine.formula_engine import FormulaEngine


class PluginLoader:
    """Loads custom formula functions from the plugins package.

    Scaffold note:
    Plugin security and sandboxing are not implemented in MVP.
    """

    def __init__(self, plugins_dir: str = "plugins") -> None:
        self.plugins_dir = Path(plugins_dir)

    def load(self, engine: FormulaEngine) -> None:
        if not self.plugins_dir.exists():
            return

        for plugin_file in self.plugins_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
            module_name = f"plugins.{plugin_file.stem}"
            module = import_module(module_name)
            for name, fn in getmembers(module, isfunction):
                if name.isupper():
                    engine.register_function(name, fn)
