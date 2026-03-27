"""Main desktop window scaffold for AI Spreadsheet MVP."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLineEdit,
    QMainWindow,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.engine.formula_engine import FormulaEngine
from app.engine.plugin_loader import PluginLoader
from app.formulas.registry import register_builtin_functions
from app.models.workbook import Workbook
from app.storage.json_storage import JsonWorkbookStorage


class MainWindow(QMainWindow):
    """MVP spreadsheet shell with core UI regions in place."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AI Spreadsheet")
        self.resize(1200, 800)

        self.storage = JsonWorkbookStorage()
        self.workbook = Workbook(name="Untitled")
        self.workbook.add_sheet("Sheet1")

        self.formula_engine = FormulaEngine()
        register_builtin_functions(self.formula_engine)
        PluginLoader().load(self.formula_engine)

        self._build_menu_bar()
        self._build_toolbar()
        self._build_central_ui()
        self._build_status_bar()

    def _build_menu_bar(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("File")
        file_menu.addAction("New")
        file_menu.addAction("Open")
        file_menu.addAction("Save")
        file_menu.addAction("Save As")

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        toolbar.addAction("Bold")
        toolbar.addAction("Italic")
        toolbar.addAction("Borders")

    def _build_central_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)

        self.formula_bar = QLineEdit()
        self.formula_bar.setPlaceholderText("Formula bar (e.g., =SUM(1,2,3))")
        self.formula_bar.returnPressed.connect(self._apply_formula_to_current_cell)
        layout.addWidget(self.formula_bar)

        self.sheet_tabs = QTabWidget()
        self.sheet_tabs.setTabsClosable(False)
        self.sheet_tabs.currentChanged.connect(self._on_sheet_changed)

        table = self._build_grid_for_sheet("Sheet1")
        self.sheet_tabs.addTab(table, "Sheet1")

        layout.addWidget(self.sheet_tabs)
        self.setCentralWidget(root)

    def _build_status_bar(self) -> None:
        bar = QStatusBar()
        bar.showMessage("Ready")
        self.setStatusBar(bar)

    def _build_grid_for_sheet(self, sheet_name: str) -> QTableWidget:
        table = QTableWidget(100, 26)
        table.setObjectName(f"grid_{sheet_name}")
        table.setHorizontalHeaderLabels([chr(ord("A") + i) for i in range(26)])
        table.itemChanged.connect(self._on_cell_changed)
        return table

    def _on_sheet_changed(self, index: int) -> None:
        self.workbook.active_sheet_index = max(0, index)
        self.statusBar().showMessage(f"Switched to sheet #{index + 1}")

    def _on_cell_changed(self, item: QTableWidgetItem) -> None:
        sheet = self.workbook.get_active_sheet()
        address = self._index_to_address(item.row(), item.column())
        cell = sheet.get_cell(address)
        text = item.text()

        if text.startswith("="):
            cell.formula = text
            cell.value = self.formula_engine.evaluate(text)
        else:
            cell.formula = None
            cell.value = text

        self.statusBar().showMessage(f"Updated {address}")

    def _apply_formula_to_current_cell(self) -> None:
        grid = self._current_grid()
        if grid is None:
            return

        current = grid.currentItem()
        if current is None:
            current = QTableWidgetItem("")
            grid.setItem(0, 0, current)

        current.setText(self.formula_bar.text())

    def _current_grid(self) -> Optional[QTableWidget]:
        widget = self.sheet_tabs.currentWidget()
        return widget if isinstance(widget, QTableWidget) else None

    @staticmethod
    def _index_to_address(row: int, col: int) -> str:
        return f"{chr(ord('A') + col)}{row + 1}"
