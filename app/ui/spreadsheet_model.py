"""Virtualised Qt model backed by sparse worksheet cells."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor, QFont

from app.core.coordinates import CellAddress, column_index_to_label
from app.models.sheet import Worksheet
from app.services.worksheet_editing import snapshot


class SpreadsheetTableModel(QAbstractTableModel):
    """Expose a large logical grid without allocating one widget per cell."""

    cell_edited = Signal(str, object, object)
    cell_editing = Signal(object)

    def __init__(self, worksheet: Worksheet, rows: int = 100_000, columns: int = 1_024,
                 evaluator: Callable[[Worksheet, str, str], Any] | None = None,
                 editable: bool = True) -> None:
        super().__init__()
        self.worksheet = worksheet
        self.logical_rows = max(rows, self._used_rows() + 100)
        self.logical_columns = max(columns, self._used_columns() + 26)
        self.evaluator = evaluator
        self.editable = editable

    def rowCount(self, _parent=QModelIndex()) -> int:
        return self.logical_rows

    def columnCount(self, _parent=QModelIndex()) -> int:
        return self.logical_columns

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        return column_index_to_label(section) if orientation == Qt.Orientation.Horizontal else str(section + 1)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        cell = self.worksheet.cells.get(self.address(index))
        if cell is None:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return "" if cell.value is None else str(cell.value)
        if role == Qt.ItemDataRole.EditRole:
            return cell.formula if cell.formula else "" if cell.value is None else str(cell.value)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            align = cell.formatting.get("horizontal_align")
            return {"center": Qt.AlignmentFlag.AlignCenter, "right": Qt.AlignmentFlag.AlignRight}.get(align)
        if role == Qt.ItemDataRole.BackgroundRole and cell.formatting.get("fill_color"):
            return QColor("#" + str(cell.formatting["fill_color"])[-6:])
        if role == Qt.ItemDataRole.ForegroundRole and cell.formatting.get("font_color"):
            return QColor("#" + str(cell.formatting["font_color"])[-6:])
        if role == Qt.ItemDataRole.FontRole:
            font = QFont()
            font.setBold(bool(cell.formatting.get("bold")))
            font.setItalic(bool(cell.formatting.get("italic")))
            font.setUnderline(bool(cell.formatting.get("underline")))
            return font
        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not self.editable or role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        self.cell_editing.emit(snapshot(self.worksheet))
        address = self.address(index)
        cell = self.worksheet.get_cell(address)
        before = deepcopy(cell.to_dict())
        text = "" if value is None else str(value)
        if text.startswith("="):
            cell.formula = text
            cell.value = self.evaluator(self.worksheet, address, text) if self.evaluator else None
        else:
            cell.formula = None
            cell.value = self._infer_scalar(text)
        after = deepcopy(cell.to_dict())
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
        self.cell_edited.emit(address, before, after)
        return True

    def flags(self, index: QModelIndex):
        flags = super().flags(index)
        return flags | Qt.ItemFlag.ItemIsEditable if self.editable else flags

    def refresh(self) -> None:
        """Notify the view after workbook-wide recalculation."""
        self.layoutChanged.emit()

    @staticmethod
    def address(index: QModelIndex) -> str:
        return CellAddress(index.row(), index.column()).a1(False)

    @staticmethod
    def _infer_scalar(text: str) -> Any:
        stripped = text.strip()
        if stripped == "":
            return None
        if stripped.lower() in {"true", "false"}:
            return stripped.lower() == "true"
        try:
            return int(stripped)
        except ValueError:
            try:
                return float(stripped)
            except ValueError:
                return text

    def _used_rows(self) -> int:
        return max((CellAddress.parse(address).row + 1 for address in self.worksheet.cells), default=0)

    def _used_columns(self) -> int:
        return max((CellAddress.parse(address).column + 1 for address in self.worksheet.cells), default=0)
