"""Dependency graph and dirty-cell scheduling for workbook recalculation."""

from __future__ import annotations

from collections import defaultdict, deque


class CircularReferenceError(ValueError):
    """Raised when a recalculation subgraph contains a cycle."""


class DependencyGraph:
    def __init__(self) -> None:
        self.dependencies: dict[str, set[str]] = defaultdict(set)
        self.dependents: dict[str, set[str]] = defaultdict(set)

    def set_dependencies(self, cell: str, references: set[str]) -> None:
        for old in self.dependencies.get(cell, set()):
            self.dependents[old].discard(cell)
        self.dependencies[cell] = set(references)
        for reference in references:
            self.dependents[reference].add(cell)

    def remove(self, cell: str) -> None:
        self.set_dependencies(cell, set())
        for dependent in self.dependents.pop(cell, set()):
            self.dependencies[dependent].discard(cell)

    def affected_by(self, changed: set[str]) -> set[str]:
        affected = set(changed)
        pending = list(changed)
        while pending:
            for dependent in self.dependents.get(pending.pop(), set()):
                if dependent not in affected:
                    affected.add(dependent)
                    pending.append(dependent)
        return affected

    def calculation_order(self, cells: set[str]) -> list[str]:
        indegree = {cell: len(self.dependencies.get(cell, set()) & cells) for cell in cells}
        queue = deque(sorted(cell for cell, degree in indegree.items() if degree == 0))
        ordered: list[str] = []
        while queue:
            cell = queue.popleft()
            ordered.append(cell)
            for dependent in sorted(self.dependents.get(cell, set()) & cells):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    queue.append(dependent)
        if len(ordered) != len(cells):
            raise CircularReferenceError("Circular reference detected")
        return ordered
