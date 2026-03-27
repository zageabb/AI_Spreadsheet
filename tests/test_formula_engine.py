"""Tests for formula engine scaffold behavior."""

from __future__ import annotations

from app.engine.formula_engine import FormulaEngine
from app.formulas.registry import register_builtin_functions


def test_sum_formula_evaluates():
    engine = FormulaEngine()
    register_builtin_functions(engine)

    assert engine.evaluate("=SUM(1,2,3)") == 6.0
