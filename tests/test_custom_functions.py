"""Tests for user-authored Python formula functions."""

from __future__ import annotations

import pytest

from app.engine.formula_engine import FormulaEngine
from app.services.custom_functions import CustomFunctionError, CustomFunctionService


def test_custom_function_is_saved_registered_and_callable(tmp_path):
    engine = FormulaEngine()
    service = CustomFunctionService(tmp_path)
    result = service.save_and_register(
        "pricing helpers",
        "def ADD_MARGIN(value, percent=10):\n    return float(value) * (1 + float(percent) / 100)\n",
        engine,
    )
    assert result.path.name == "pricing_helpers.py"
    assert result.function_names == ("ADD_MARGIN",)
    assert engine.evaluate("=ADD_MARGIN(100,15)") == pytest.approx(115.0)


@pytest.mark.parametrize(
    "source",
    [
        "import os\ndef BAD():\n    return os.getcwd()\n",
        "def BAD():\n    return open('secret.txt').read()\n",
        "def BAD(value):\n    return value.__class__\n",
        "def BAD(value):\n    return getattr(value, 'secret')\n",
        "def lower(value):\n    return value\n",
    ],
)
def test_custom_function_rejects_unsafe_or_invalid_source(tmp_path, source):
    service = CustomFunctionService(tmp_path)
    with pytest.raises(CustomFunctionError):
        service.validate(source)
