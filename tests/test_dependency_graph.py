import pytest
from app.engine.dependency_graph import CircularReferenceError, DependencyGraph


def test_affected_cells_and_order():
    graph = DependencyGraph(); graph.set_dependencies("B1", {"A1"}); graph.set_dependencies("C1", {"B1"})
    assert graph.affected_by({"A1"}) == {"A1", "B1", "C1"}
    assert graph.calculation_order({"A1", "B1", "C1"}) == ["A1", "B1", "C1"]


def test_cycle_is_reported():
    graph = DependencyGraph(); graph.set_dependencies("A1", {"B1"}); graph.set_dependencies("B1", {"A1"})
    with pytest.raises(CircularReferenceError): graph.calculation_order({"A1", "B1"})
