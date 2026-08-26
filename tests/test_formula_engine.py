"""Tests for formula parsing, evaluation, and runtime function loading."""

from __future__ import annotations

from app.engine.formula_engine import FormulaEngine
from app.engine.plugin_loader import PluginLoader
from app.formulas.registry import register_builtin_functions


def _build_engine() -> FormulaEngine:
    engine = FormulaEngine()
    register_builtin_functions(engine)
    return engine


def test_starter_function_set_is_registered() -> None:
    engine = _build_engine()
    for fn_name in [
        "SUM",
        "AVERAGE",
        "MIN",
        "MAX",
        "COUNT",
        "IF",
        "AND",
        "OR",
        "NOT",
        "ROUND",
        "ABS",
        "CONCAT",
        "LEFT",
        "RIGHT",
        "LEN",
        "VLOOKUP",
        "XLOOKUP",
        "INDEX",
        "MATCH",
        "COUNTIF",
        "SUMIF",
        "DATE",
        "TODAY",
        "TEXTJOIN",
        "SUMPRODUCT",
    ]:
        assert engine.has_function(fn_name)


def test_formula_supports_same_sheet_reference() -> None:
    engine = _build_engine()
    sheet_values = {"A1": 10, "B2": 5}

    result = engine.evaluate("=A1+B2", context={"get_cell_value": lambda ref: sheet_values.get(ref, 0)})

    assert result == 15.0


def test_formula_supports_ranges_and_absolute_references() -> None:
    engine = _build_engine()
    values = {"$A$1": 10, "A2": 5, "A3": 2}
    result = engine.evaluate(
        "=SUM($A$1:A3)",
        context={
            "get_cell_value": lambda ref: values.get(ref),
            "get_range_values": lambda start, end: [values["$A$1"], values["A2"], values["A3"]],
        },
    )
    assert result == 17.0


def test_formula_supports_quoted_cross_sheet_reference() -> None:
    engine = _build_engine()
    assert engine.evaluate(
        "='Sales Data'!B2*2",
        context={"get_cell_value": lambda ref: 12 if ref == "'Sales Data'!B2" else None},
    ) == 24.0


def test_formula_supports_nested_function_calls_and_comparison() -> None:
    engine = _build_engine()
    result = engine.evaluate("=IF(SUM(1,2,3)=6, CONCAT(\"ok\", \"!\"), \"bad\")")
    assert result == "ok!"


def test_formula_supports_unary_minus_and_parentheses() -> None:
    engine = _build_engine()
    assert engine.evaluate("=-(2+3)") == -5.0


def test_formula_returns_error_for_invalid_syntax() -> None:
    engine = _build_engine()
    assert engine.evaluate("=SUM(1,2") == "#PARSE!"


def test_formula_returns_parse_error_for_invalid_token() -> None:
    engine = _build_engine()
    assert engine.evaluate("=1+@")=="#PARSE!"


def test_formula_returns_name_error_for_missing_function() -> None:
    engine = _build_engine()
    assert engine.evaluate("=MISSING_FN(1)") == "#NAME?"


def test_formula_propagates_resolved_cell_errors() -> None:
    engine = _build_engine()
    assert engine.evaluate("=A1", context={"get_cell_value": lambda _ref: "#DIV/0!"}) == "#DIV/0!"


def test_divide_by_zero_error() -> None:
    engine = _build_engine()
    assert engine.evaluate("=1/0") == "#DIV/0!"


def test_plugin_loader_loads_uppercase_runtime_functions(tmp_path) -> None:
    engine = _build_engine()
    plugin_file = tmp_path / "my_plugin.py"
    plugin_file.write_text(
        "def DOUBLE(value):\n"
        "    return float(value) * 2\n\n"
        "def helper(value):\n"
        "    return value\n",
        encoding="utf-8",
    )

    loaded = PluginLoader(plugins_dir=str(tmp_path)).load(engine)

    assert "DOUBLE" in loaded
    assert engine.evaluate("=DOUBLE(7)") == 14.0
