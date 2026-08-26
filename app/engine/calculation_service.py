"""Workbook-wide dependency tracking and recalculation."""

from __future__ import annotations

from app.core.coordinates import CellAddress, CellRange
from app.engine.dependency_graph import CircularReferenceError, DependencyGraph
from app.engine.formula_engine import FormulaEngine, RangeValue
from app.models.workbook import Workbook


class WorkbookCalculationService:
    """Evaluate formulas consistently across all worksheets in a workbook."""

    def __init__(self, workbook: Workbook, engine: FormulaEngine) -> None:
        self.workbook = workbook
        self.engine = engine
        self.graph = DependencyGraph()
        self._formula_cells: dict[str, tuple[str, str]] = {}

    @staticmethod
    def cell_key(sheet_name: str, address: str) -> str:
        return f"{sheet_name}!{CellAddress.parse(address).a1(False)}"

    def rebuild_graph(self) -> None:
        self.graph = DependencyGraph()
        self._formula_cells.clear()
        for sheet in self.workbook.sheets:
            for address, cell in sheet.cells.items():
                if not cell.formula:
                    continue
                key = self.cell_key(sheet.name, address)
                self._formula_cells[key] = (sheet.name, address)
                references = self._formula_dependencies(cell.formula, sheet.name)
                self.graph.set_dependencies(key, references)

    def recalculate(self, changed: set[str] | None = None) -> set[str]:
        """Recalculate changed cells and all downstream dependents."""
        self.rebuild_graph()
        targets = set(self._formula_cells) if changed is None else self.graph.affected_by(changed)
        try:
            order = self.graph.calculation_order(targets)
        except CircularReferenceError:
            for key in targets & self._formula_cells.keys():
                sheet_name, address = self._formula_cells[key]
                self._sheet(sheet_name).get_cell(address).value = "#CIRC!"
            return targets

        for key in order:
            details = self._formula_cells.get(key)
            if details is None:
                continue
            sheet_name, address = details
            cell = self._sheet(sheet_name).get_cell(address)
            cell.value = self.evaluate_formula(sheet_name, cell.formula or "")
        return targets

    def evaluate_formula(self, current_sheet: str, formula: str):
        context = {
            "get_cell_value": lambda reference: self._value(reference, current_sheet),
            "get_range_values": lambda start, end: self._range_values(start, end, current_sheet),
        }
        return self.engine.evaluate(formula, context)

    def _formula_dependencies(self, formula: str, current_sheet: str) -> set[str]:
        references = self.engine.extract_references(formula)
        dependencies: set[str] = set()
        tokens = self._reference_groups(formula)
        ranged_refs: set[str] = set()
        for start, end in tokens:
            dependencies.update(self._range_keys(start, end, current_sheet))
            ranged_refs.update({start, end})
        for reference in references - ranged_refs:
            dependencies.add(self._key_from_reference(reference, current_sheet))
        return dependencies

    @staticmethod
    def _reference_groups(formula: str) -> list[tuple[str, str]]:
        from app.engine.formula_engine import _tokenize
        tokens = _tokenize(formula.lstrip("="))
        groups: list[tuple[str, str]] = []
        for index in range(len(tokens) - 2):
            if tokens[index].kind == "CELL" and tokens[index + 1].kind == "COLON" and tokens[index + 2].kind == "CELL":
                groups.append((tokens[index].value, tokens[index + 2].value))
        return groups

    def _value(self, reference: str, current_sheet: str):
        address = CellAddress.parse(reference)
        sheet = self._sheet(address.sheet or current_sheet)
        cell = sheet.cells.get(address.a1(False))
        return cell.value if cell else None

    def _range_values(self, start: str, end: str, current_sheet: str) -> RangeValue:
        first = CellAddress.parse(start)
        sheet_name = first.sheet or current_sheet
        keys = self._range_keys(start, end, current_sheet)
        second = CellAddress.parse(end)
        height = abs(second.row - first.row) + 1
        width = abs(second.column - first.column) + 1
        flat_values = []
        for key in keys:
            resolved_sheet, address = key.rsplit("!", 1)
            cell = self._sheet(resolved_sheet).cells.get(address)
            flat_values.append(cell.value if cell else None)
        rows = [flat_values[index:index + width] for index in range(0, height * width, width)]
        return RangeValue(rows)

    def _range_keys(self, start: str, end: str, current_sheet: str) -> list[str]:
        first = CellAddress.parse(start)
        if first.sheet is None:
            first = CellAddress(first.row, first.column, current_sheet, first.absolute_row, first.absolute_column)
        second = CellAddress.parse(end)
        if second.sheet is None:
            second = CellAddress(second.row, second.column, first.sheet, second.absolute_row, second.absolute_column)
        cell_range = CellRange(first, second)
        return [self.cell_key(item.sheet or current_sheet, item.a1(False)) for item in cell_range.addresses()]

    def _key_from_reference(self, reference: str, current_sheet: str) -> str:
        address = CellAddress.parse(reference)
        return self.cell_key(address.sheet or current_sheet, address.a1(False))

    def _sheet(self, name: str):
        for sheet in self.workbook.sheets:
            if sheet.name == name:
                return sheet
        raise KeyError(f"Unknown worksheet: {name}")
