"""Runtime plugin loader for user-defined formula functions."""

from __future__ import annotations

from importlib import util
from inspect import getmembers, isfunction
from pathlib import Path

from app.engine.formula_engine import FormulaEngine


class PluginLoader:
    """Loads custom formula functions from Python modules in ``plugins/``.

    Plugin contract:
    - Every ``.py`` file in the plugin folder is considered.
    - Uppercase function names (e.g., ``MYFUNC``) are registered.
    - Invalid modules are skipped so one bad plugin does not break startup.
    """

    def __init__(self, plugins_dir: str = "plugins") -> None:
        self.plugins_dir = Path(plugins_dir)

    def load(self, engine: FormulaEngine) -> list[str]:
        """Load plugin functions and return a list of function names registered."""
        registered: list[str] = []
        if not self.plugins_dir.exists():
            return registered

        for plugin_file in sorted(self.plugins_dir.glob("*.py")):
            if plugin_file.name.startswith("_"):
                continue

            module_name = f"plugins_runtime_{plugin_file.stem}"
            spec = util.spec_from_file_location(module_name, plugin_file)
            if spec is None or spec.loader is None:
                continue

            module = util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception:  # noqa: BLE001 - skip invalid plugin module
                continue

            for name, fn in getmembers(module, isfunction):
                if name.isupper():
                    engine.register_function(name, fn)
                    registered.append(name)

        return sorted(set(registered))
