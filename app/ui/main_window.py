"""Main desktop window scaffold for AI Spreadsheet MVP."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QLabel,
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
    """Desktop spreadsheet shell with improved usability and UI behavior."""

    ROW_COUNT = 100
    COL_COUNT = 26

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AI Spreadsheet")
        self.resize(1280, 820)

        self.storage = JsonWorkbookStorage()
        self.workbook = Workbook(name="Untitled")
        self.workbook.add_sheet("Sheet1")
        self.current_file_path: Optional[str] = None

        self.formula_engine = FormulaEngine()
        register_builtin_functions(self.formula_engine)
        PluginLoader().load(self.formula_engine)

        self._suppress_cell_events = False
        self._undo_stack: list[dict[str, Any]] = []
        self._redo_stack: list[dict[str, Any]] = []

        self._create_actions()
        self._build_menu_bar()
        self._build_toolbar()
        self._build_central_ui()
        self._build_status_bar()
        self._refresh_window_title()

    def _create_actions(self) -> None:
        self.action_new = QAction("New", self)
        self.action_new.setShortcut(QKeySequence.StandardKey.New)
        self.action_new.triggered.connect(self._new_workbook)

        self.action_open = QAction("Open...", self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.triggered.connect(self._open_workbook)

        self.action_save = QAction("Save", self)
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        self.action_save.triggered.connect(self._save_workbook)

        self.action_save_as = QAction("Save As...", self)
        self.action_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.action_save_as.triggered.connect(self._save_workbook_as)

        self.action_copy = QAction("Copy", self)
        self.action_copy.setShortcut(QKeySequence.StandardKey.Copy)
        self.action_copy.triggered.connect(self._copy_selection)

        self.action_paste = QAction("Paste", self)
        self.action_paste.setShortcut(QKeySequence.StandardKey.Paste)
        self.action_paste.triggered.connect(self._paste_into_grid)

        self.action_undo = QAction("Undo", self)
        self.action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.action_undo.triggered.connect(self._undo)

        self.action_redo = QAction("Redo", self)
        self.action_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.action_redo.triggered.connect(self._redo)

        self.action_add_sheet = QAction("Add Sheet", self)
        self.action_add_sheet.setShortcut("Ctrl+Shift+N")
        self.action_add_sheet.triggered.connect(self._add_sheet)

        self.action_rename_sheet = QAction("Rename Sheet", self)
        self.action_rename_sheet.triggered.connect(self._rename_sheet)

        self.action_duplicate_sheet = QAction("Duplicate Sheet", self)
        self.action_duplicate_sheet.triggered.connect(self._duplicate_sheet)

        self.action_delete_sheet = QAction("Delete Sheet", self)
        self.action_delete_sheet.triggered.connect(self._delete_sheet)

    def _build_menu_bar(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("File")
        file_menu.addAction(self.action_new)
        file_menu.addAction(self.action_open)
        file_menu.addSeparator()
        file_menu.addAction(self.action_save)
        file_menu.addAction(self.action_save_as)

        edit_menu = menu.addMenu("Edit")
        edit_menu.addAction(self.action_undo)
        edit_menu.addAction(self.action_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.action_copy)
        edit_menu.addAction(self.action_paste)

        sheet_menu = menu.addMenu("Sheet")
        sheet_menu.addAction(self.action_add_sheet)
        sheet_menu.addAction(self.action_rename_sheet)
        sheet_menu.addAction(self.action_duplicate_sheet)
        sheet_menu.addAction(self.action_delete_sheet)

    def _build_toolbar(self) -> None:
        file_toolbar = QToolBar("File")
        file_toolbar.setMovable(False)
        self.addToolBar(file_toolbar)
        file_toolbar.addAction(self.action_new)
        file_toolbar.addAction(self.action_open)
        file_toolbar.addAction(self.action_save)

        edit_toolbar = QToolBar("Edit")
        edit_toolbar.setMovable(False)
        self.addToolBar(edit_toolbar)
        edit_toolbar.addAction(self.action_undo)
        edit_toolbar.addAction(self.action_redo)
        edit_toolbar.addSeparator()
        edit_toolbar.addAction(self.action_copy)
        edit_toolbar.addAction(self.action_paste)

    def _build_central_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        formula_row = QHBoxLayout()
        formula_row.setSpacing(6)

        self.name_box = QLineEdit()
        self.name_box.setReadOnly(True)
        self.name_box.setFixedWidth(80)
        self.name_box.setPlaceholderText("A1")
        formula_row.addWidget(self.name_box)

        self.formula_bar = QLineEdit()
        self.formula_bar.setPlaceholderText("Enter a value or formula (e.g., =SUM(1,2,3))")
        self.formula_bar.returnPressed.connect(self._apply_formula_to_current_cell)
        formula_row.addWidget(self.formula_bar)

        layout.addLayout(formula_row)

        self.sheet_tabs = QTabWidget()
        self.sheet_tabs.setTabsClosable(False)
        self.sheet_tabs.setMovable(True)
        self.sheet_tabs.currentChanged.connect(self._on_sheet_changed)

        self._rebuild_sheet_tabs()

        layout.addWidget(self.sheet_tabs)
        self.setCentralWidget(root)

    def _build_status_bar(self) -> None:
        bar = QStatusBar()
        self.status_position = QLabel("Cell: -")
        self.status_mode = QLabel("Mode: Ready")
        bar.addPermanentWidget(self.status_position)
        bar.addPermanentWidget(self.status_mode)
        bar.showMessage("Ready")
        self.setStatusBar(bar)

    def _rebuild_sheet_tabs(self) -> None:
        self.sheet_tabs.blockSignals(True)
        self.sheet_tabs.clear()
        for sheet in self.workbook.sheets:
            table = self._build_grid_for_sheet(sheet.name)
            self.sheet_tabs.addTab(table, sheet.name)
            self._load_sheet_into_grid(sheet.name, table)

        active_index = min(self.workbook.active_sheet_index, self.sheet_tabs.count() - 1)
        self.sheet_tabs.setCurrentIndex(max(0, active_index))
        self.sheet_tabs.blockSignals(False)

    def _build_grid_for_sheet(self, sheet_name: str) -> QTableWidget:
        table = QTableWidget(self.ROW_COUNT, self.COL_COUNT)
        table.setObjectName(f"grid_{sheet_name}")
        table.setHorizontalHeaderLabels([self._column_label(i) for i in range(self.COL_COUNT)])
        table.setVerticalHeaderLabels([str(i + 1) for i in range(self.ROW_COUNT)])
        table.setAlternatingRowColors(True)
        table.setSelectionMode(QTableWidget.SelectionMode.ContiguousSelection)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        table.horizontalHeader().setDefaultSectionSize(110)
        table.verticalHeader().setDefaultSectionSize(24)
        table.itemChanged.connect(self._on_cell_changed)
        table.currentCellChanged.connect(self._on_current_cell_changed)
        return table

    def _load_sheet_into_grid(self, sheet_name: str, table: QTableWidget) -> None:
        sheet = next((s for s in self.workbook.sheets if s.name == sheet_name), None)
        if sheet is None:
            return

        self._suppress_cell_events = True
        for address, cell in sheet.cells.items():
            row, col = self._address_to_index(address)
            if not (0 <= row < self.ROW_COUNT and 0 <= col < self.COL_COUNT):
                continue
            item = table.item(row, col) or QTableWidgetItem("")
            item.setText("" if cell.value is None else str(cell.value))
            table.setItem(row, col, item)
        self._suppress_cell_events = False

    def _on_sheet_changed(self, index: int) -> None:
        if index < 0:
            return
        self.workbook.active_sheet_index = index
        self.statusBar().showMessage(f"Switched to {self.workbook.get_active_sheet().name}", 2500)
        grid = self._current_grid()
        if grid is not None:
            self._on_current_cell_changed(
                grid.currentRow(),
                grid.currentColumn(),
                grid.currentRow(),
                grid.currentColumn(),
            )

    def _on_current_cell_changed(self, current_row: int, current_col: int, _prev_row: int, _prev_col: int) -> None:
        if current_row < 0 or current_col < 0:
            self.name_box.clear()
            self.formula_bar.clear()
            self.status_position.setText("Cell: -")
            return

        address = self._index_to_address(current_row, current_col)
        sheet = self.workbook.get_active_sheet()
        cell = sheet.get_cell(address)

        self.name_box.setText(address)
        self.formula_bar.setText(cell.formula if cell.formula else "" if cell.value is None else str(cell.value))
        self.status_position.setText(f"Cell: {address}")

    def _on_cell_changed(self, item: QTableWidgetItem) -> None:
        if self._suppress_cell_events:
            return
        self._set_cell_from_user_input(item.row(), item.column(), item.text(), record_undo=True)

    def _set_cell_from_user_input(self, row: int, col: int, user_text: str, record_undo: bool = True) -> None:
        sheet = self.workbook.get_active_sheet()
        address = self._index_to_address(row, col)
        cell = sheet.get_cell(address)
        before_state = {"formula": cell.formula, "value": cell.value}

        if user_text.startswith("="):
            result = self.formula_engine.evaluate(user_text)
            cell.formula = user_text
            cell.value = result
            display_value = "" if result is None else str(result)
        else:
            cell.formula = None
            cell.value = user_text
            display_value = user_text

        self._suppress_cell_events = True
        table_item = self._current_grid().item(row, col) if self._current_grid() else None
        if table_item is None and self._current_grid() is not None:
            table_item = QTableWidgetItem("")
            self._current_grid().setItem(row, col, table_item)
        if table_item is not None:
            table_item.setText(display_value)
        self._suppress_cell_events = False

        after_state = {"formula": cell.formula, "value": cell.value}
        if record_undo:
            self._push_undo([{"row": row, "col": col, "before": before_state, "after": after_state}])

        self.formula_bar.setText(user_text)
        self.status_mode.setText("Mode: Edit")
        self.statusBar().showMessage(f"Updated {address}", 2000)

    def _apply_formula_to_current_cell(self) -> None:
        grid = self._current_grid()
        if grid is None:
            return

        row = max(0, grid.currentRow())
        col = max(0, grid.currentColumn())
        self._set_cell_from_user_input(row, col, self.formula_bar.text(), record_undo=True)
        grid.setCurrentCell(row, col)

    def _copy_selection(self) -> None:
        grid = self._current_grid()
        if grid is None:
            return

        selected = grid.selectedRanges()
        if not selected:
            return

        selection = selected[0]
        lines: list[str] = []
        for row in range(selection.topRow(), selection.bottomRow() + 1):
            cells: list[str] = []
            for col in range(selection.leftColumn(), selection.rightColumn() + 1):
                item = grid.item(row, col)
                cells.append(item.text() if item else "")
            lines.append("\t".join(cells))

        QApplication.clipboard().setText("\n".join(lines))
        self.statusBar().showMessage("Copied selection", 1500)

    def _paste_into_grid(self) -> None:
        grid = self._current_grid()
        if grid is None:
            return

        row_start = max(0, grid.currentRow())
        col_start = max(0, grid.currentColumn())
        raw = QApplication.clipboard().text()
        if not raw:
            return

        edits: list[dict[str, Any]] = []
        for row_offset, line in enumerate(raw.splitlines()):
            for col_offset, value in enumerate(line.split("\t")):
                row = row_start + row_offset
                col = col_start + col_offset
                if row >= self.ROW_COUNT or col >= self.COL_COUNT:
                    continue

                sheet = self.workbook.get_active_sheet()
                address = self._index_to_address(row, col)
                cell = sheet.get_cell(address)
                before_state = {"formula": cell.formula, "value": cell.value}
                self._set_cell_from_user_input(row, col, value, record_undo=False)
                after_state = {"formula": cell.formula, "value": cell.value}
                edits.append({"row": row, "col": col, "before": before_state, "after": after_state})

        if edits:
            self._push_undo(edits)
            self.statusBar().showMessage("Pasted clipboard contents", 1500)

    def _push_undo(self, edits: list[dict[str, Any]]) -> None:
        self._undo_stack.append({"edits": edits})
        self._redo_stack.clear()

    def _undo(self) -> None:
        if not self._undo_stack:
            self.statusBar().showMessage("Nothing to undo", 1500)
            return

        command = self._undo_stack.pop()
        for edit in command["edits"]:
            self._apply_cell_state(edit["row"], edit["col"], edit["before"])
        self._redo_stack.append(command)
        self.status_mode.setText("Mode: Undo")
        self.statusBar().showMessage("Undo", 1200)

    def _redo(self) -> None:
        if not self._redo_stack:
            self.statusBar().showMessage("Nothing to redo", 1500)
            return

        command = self._redo_stack.pop()
        for edit in command["edits"]:
            self._apply_cell_state(edit["row"], edit["col"], edit["after"])
        self._undo_stack.append(command)
        self.status_mode.setText("Mode: Redo")
        self.statusBar().showMessage("Redo", 1200)

    def _apply_cell_state(self, row: int, col: int, state: dict[str, Any]) -> None:
        sheet = self.workbook.get_active_sheet()
        address = self._index_to_address(row, col)
        cell = sheet.get_cell(address)
        cell.formula = state.get("formula")
        cell.value = state.get("value")

        display = "" if cell.value is None else str(cell.value)
        grid = self._current_grid()
        if grid is None:
            return

        self._suppress_cell_events = True
        item = grid.item(row, col) or QTableWidgetItem("")
        item.setText(display)
        grid.setItem(row, col, item)
        self._suppress_cell_events = False

    def _new_workbook(self) -> None:
        self.workbook = Workbook(name="Untitled")
        self.workbook.add_sheet("Sheet1")
        self.current_file_path = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._rebuild_sheet_tabs()
        self._refresh_window_title()
        self.statusBar().showMessage("Created new workbook", 2000)

    def _open_workbook(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Workbook", "", "JSON Workbook (*.json)")
        if not path:
            return

        try:
            self.workbook = self.storage.load_workbook(path)
        except OSError as error:
            QMessageBox.warning(self, "Open Failed", f"Could not open workbook:\n{error}")
            return

        self.current_file_path = path
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._rebuild_sheet_tabs()
        self._refresh_window_title()
        self.statusBar().showMessage(f"Opened {path}", 2000)

    def _save_workbook(self) -> None:
        if self.current_file_path is None:
            self._save_workbook_as()
            return

        self.storage.save_workbook(self.current_file_path, self.workbook)
        self.statusBar().showMessage(f"Saved {self.current_file_path}", 2000)

    def _save_workbook_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Workbook As", "", "JSON Workbook (*.json)")
        if not path:
            return
        if not path.endswith(".json"):
            path = f"{path}.json"

        self.storage.save_workbook(path, self.workbook)
        self.current_file_path = path
        self._refresh_window_title()
        self.statusBar().showMessage(f"Saved {path}", 2000)

    def _add_sheet(self) -> None:
        base_name = f"Sheet{len(self.workbook.sheets) + 1}"
        name, accepted = QInputDialog.getText(self, "Add Sheet", "Sheet name:", text=base_name)
        if not accepted:
            return

        sheet_name = name.strip() or base_name
        self.workbook.add_sheet(sheet_name)
        table = self._build_grid_for_sheet(sheet_name)
        self.sheet_tabs.addTab(table, sheet_name)
        self.sheet_tabs.setCurrentWidget(table)
        self.statusBar().showMessage(f"Added sheet {sheet_name}", 2000)

    def _rename_sheet(self) -> None:
        index = self.sheet_tabs.currentIndex()
        if index < 0:
            return

        sheet = self.workbook.sheets[index]
        new_name, accepted = QInputDialog.getText(self, "Rename Sheet", "Sheet name:", text=sheet.name)
        if not accepted:
            return

        normalized = new_name.strip()
        if not normalized:
            QMessageBox.information(self, "Rename Sheet", "Sheet name cannot be empty.")
            return

        sheet.name = normalized
        self.sheet_tabs.setTabText(index, normalized)
        self.statusBar().showMessage(f"Renamed sheet to {normalized}", 2000)

    def _duplicate_sheet(self) -> None:
        index = self.sheet_tabs.currentIndex()
        if index < 0:
            return

        source = self.workbook.sheets[index]
        duplicate = self.workbook.add_sheet(f"{source.name} Copy")
        for address, cell in source.cells.items():
            new_cell = duplicate.get_cell(address)
            new_cell.value = cell.value
            new_cell.formula = cell.formula
            new_cell.formatting = dict(cell.formatting)

        table = self._build_grid_for_sheet(duplicate.name)
        self.sheet_tabs.addTab(table, duplicate.name)
        self._load_sheet_into_grid(duplicate.name, table)
        self.sheet_tabs.setCurrentWidget(table)
        self.statusBar().showMessage(f"Duplicated sheet {source.name}", 2000)

    def _delete_sheet(self) -> None:
        if len(self.workbook.sheets) <= 1:
            QMessageBox.information(self, "Delete Sheet", "At least one sheet must remain.")
            return

        index = self.sheet_tabs.currentIndex()
        if index < 0:
            return

        sheet_name = self.workbook.sheets[index].name
        del self.workbook.sheets[index]
        self.sheet_tabs.removeTab(index)
        self.workbook.active_sheet_index = max(0, min(index, len(self.workbook.sheets) - 1))
        self.sheet_tabs.setCurrentIndex(self.workbook.active_sheet_index)
        self.statusBar().showMessage(f"Deleted sheet {sheet_name}", 2000)

    def _refresh_window_title(self) -> None:
        title_suffix = self.current_file_path if self.current_file_path else self.workbook.name
        self.setWindowTitle(f"AI Spreadsheet - {title_suffix}")

    def _current_grid(self) -> Optional[QTableWidget]:
        widget = self.sheet_tabs.currentWidget()
        return widget if isinstance(widget, QTableWidget) else None

    @staticmethod
    def _column_label(col: int) -> str:
        return f"{chr(ord('A') + col)}"

    @staticmethod
    def _index_to_address(row: int, col: int) -> str:
        return f"{MainWindow._column_label(col)}{row + 1}"

    @staticmethod
    def _address_to_index(address: str) -> tuple[int, int]:
        column_chars = ""
        row_chars = ""
        for char in address:
            if char.isalpha():
                column_chars += char.upper()
            elif char.isdigit():
                row_chars += char

        if not column_chars or not row_chars:
            return 0, 0

        col = ord(column_chars[0]) - ord("A")
        row = int(row_chars) - 1
        return row, col
