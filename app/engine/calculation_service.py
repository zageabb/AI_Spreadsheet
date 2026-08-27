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
        self._spill_cells: dict[str, set[str]] = {}

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
        self._clear_previous_spills()
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
            result = self.evaluate_formula(sheet_name, cell.formula or "")
            if isinstance(result, RangeValue):
                cell.value = self._spill_array(key, sheet_name, address, result)
            else:
                cell.value = result
        spilled_keys = set().union(*self._spill_cells.values()) if self._spill_cells else set()
        if spilled_keys:
            downstream = self.graph.affected_by(spilled_keys) & self._formula_cells.keys()
            for key in self.graph.calculation_order(downstream):
                details = self._formula_cells.get(key)
                if details is None or key in self._spill_cells:
                    continue
                sheet_name, address = details
                cell = self._sheet(sheet_name).get_cell(address)
                cell.value = self.evaluate_formula(sheet_name, cell.formula or "")
        return targets

    def evaluate_formula(self, current_sheet: str, formula: str):
        context = {
            "get_cell_value": lambda reference: self._value(reference, current_sheet),
            "get_range_values": lambda start, end: self._range_values(start, end, current_sheet),
            "get_structured_values": lambda reference: self._structured_values(reference),
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
        for reference in self.engine.extract_structured_references(formula):
            sheet_name, start, end = self._structured_range(reference)
            dependencies.update(self._range_keys(start, end, sheet_name))
        return dependencies

    def _clear_previous_spills(self) -> None:
        for keys in self._spill_cells.values():
            for key in keys:
                sheet_name, address = key.rsplit("!", 1)
                cell = self._sheet(sheet_name).cells.get(address)
                if cell is not None and cell.formula is None:
                    cell.value = None
        self._spill_cells.clear()

    def _spill_array(
        self, anchor_key: str, sheet_name: str, anchor_address: str, result: RangeValue
    ):
        anchor = CellAddress.parse(anchor_address)
        targets: list[tuple[str, Any]] = []
        for row_offset, row in enumerate(result):
            for column_offset, value in enumerate(row):
                address = CellAddress(anchor.row + row_offset, anchor.column + column_offset).a1(False)
                cell = self._sheet(sheet_name).cells.get(address)
                if address != anchor_address and cell is not None and (
                    cell.formula is not None or cell.value not in (None, "")
                ):
                    return "#SPILL!"
                targets.append((address, value))
        spilled: set[str] = set()
        for address, value in targets:
            if address == anchor_address:
                continue
            self._sheet(sheet_name).get_cell(address).value = value
            spilled.add(self.cell_key(sheet_name, address))
        self._spill_cells[anchor_key] = spilled
        return result[0][0] if result and result[0] else None

    def _structured_values(self, reference: str) -> RangeValue:
        sheet_name, start, end = self._structured_range(reference)
        return self._range_values(start, end, sheet_name)

    def _structured_range(self, reference: str) -> tuple[str, str, str]:
        table_name, column_name = reference.split("[", 1)
        column_name = column_name[:-1].strip()
        for sheet in self.workbook.sheets:
            tables = sheet.metadata.get("tables", [])
            for table in tables if isinstance(tables, list) else []:
                if not isinstance(table, dict):
                    continue
                names = {str(table.get("name", "")).lower(), str(table.get("display_name", "")).lower()}
                if table_name.lower() not in names:
                    continue
                columns = [str(item) for item in table.get("columns", [])]
                try:
                    column_index = next(i for i, item in enumerate(columns) if item.lower() == column_name.lower())
                except StopIteration as exc:
                    raise KeyError(f"Unknown table column: {reference}") from exc
                first_text, last_text = str(table["ref"]).split(":", 1)
                first, last = CellAddress.parse(first_text), CellAddress.parse(last_text)
                data_start = first.row + 1
                data_end = last.row - (1 if table.get("totals_row_shown") else 0)
                if data_end < data_start:
                    raise KeyError(f"Table has no data rows: {table_name}")
                column = first.column + column_index
                start = CellAddress(data_start, column).a1(False)
                end = CellAddress(data_end, column).a1(False)
                return sheet.name, start, end
        raise KeyError(f"Unknown table reference: {reference}")

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
