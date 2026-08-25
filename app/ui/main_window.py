"""Context Studio-styled desktop shell with a virtual spreadsheet grid."""
from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QStatusBar,
    QTabWidget, QTableView, QToolBar, QVBoxLayout, QWidget)

from app.core.coordinates import CellAddress
from app.engine.formula_engine import FormulaEngine
from app.engine.plugin_loader import PluginLoader
from app.formulas.registry import register_builtin_functions
from app.models.sheet import Worksheet
from app.models.workbook import Workbook
from app.services.file_conversion import WorkbookConversionError, WorkbookFileConverter
from app.storage.json_storage import JsonWorkbookStorage
from app.ui.spreadsheet_model import SpreadsheetTableModel
from app.ui.theme import CONTEXT_STUDIO_QSS


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.resize(1400, 860); self.setStyleSheet(CONTEXT_STUDIO_QSS)
        self.storage, self.converter = JsonWorkbookStorage(), WorkbookFileConverter()
        self.engine = FormulaEngine(); register_builtin_functions(self.engine); PluginLoader().load(self.engine)
        self.workbook = Workbook(name="Untitled"); self.workbook.add_sheet("Sheet1")
        self.current_file_path: str | None = None; self.dirty = False
        self._actions(); self._chrome(); self._tabs(); self._title()

    def _make_action(self, label, shortcut, callback):
        action = QAction(label, self)
        if shortcut: action.setShortcut(shortcut)
        action.triggered.connect(callback); return action

    def _actions(self):
        self.new_a=self._make_action("New",QKeySequence.StandardKey.New,self._new)
        self.open_a=self._make_action("Open",QKeySequence.StandardKey.Open,self._open)
        self.save_a=self._make_action("Save",QKeySequence.StandardKey.Save,self._save)
        self.saveas_a=self._make_action("Save As",QKeySequence.StandardKey.SaveAs,self._save_as)
        self.xlsx_in=self._make_action("Import Excel",None,lambda:self._import("xlsx"))
        self.csv_in=self._make_action("Import CSV",None,lambda:self._import("csv"))
        self.xlsx_out=self._make_action("Export Excel",None,lambda:self._export("xlsx"))
        self.csv_out=self._make_action("Export CSV",None,lambda:self._export("csv"))
        self.add_a=self._make_action("Add Sheet","Ctrl+Shift+N",self._add_sheet)
        self.rename_a=self._make_action("Rename Sheet",None,self._rename_sheet)
        self.delete_a=self._make_action("Delete Sheet",None,self._delete_sheet)
        self.copy_a=self._make_action("Copy",QKeySequence.StandardKey.Copy,self._copy)
        self.paste_a=self._make_action("Paste",QKeySequence.StandardKey.Paste,self._paste)

    def _chrome(self):
        file_menu=self.menuBar().addMenu("File"); file_menu.addActions([self.new_a,self.open_a,self.save_a,self.saveas_a,self.xlsx_in,self.csv_in,self.xlsx_out,self.csv_out])
        edit_menu=self.menuBar().addMenu("Edit"); edit_menu.addActions([self.copy_a,self.paste_a])
        sheet_menu=self.menuBar().addMenu("Sheet"); sheet_menu.addActions([self.add_a,self.rename_a,self.delete_a])
        bar=QToolBar("Workbook"); bar.setMovable(False); bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        bar.addActions([self.new_a,self.open_a,self.save_a]); bar.addSeparator(); bar.addActions([self.copy_a,self.paste_a]); bar.addSeparator(); bar.addAction(self.add_a); self.addToolBar(bar)
        root=QWidget(); layout=QVBoxLayout(root); layout.setContentsMargins(10,10,10,8)
        formula=QHBoxLayout(); self.name_box=QLineEdit("A1"); self.name_box.setFixedWidth(90); self.name_box.returnPressed.connect(self._go)
        self.formula_bar=QLineEdit(); self.formula_bar.setPlaceholderText("Enter a value or formula"); self.formula_bar.returnPressed.connect(self._apply_formula)
        formula.addWidget(self.name_box); formula.addWidget(QLabel("fx")); formula.addWidget(self.formula_bar); layout.addLayout(formula)
        self.tabs=QTabWidget(); self.tabs.setDocumentMode(True); self.tabs.setMovable(True); self.tabs.currentChanged.connect(self._tab_changed)
        plus=QPushButton("+"); plus.clicked.connect(self._add_sheet); self.tabs.setCornerWidget(plus); layout.addWidget(self.tabs); self.setCentralWidget(root)
        status=QStatusBar(); self.cell_status=QLabel("Cell: A1"); self.selection_status=QLabel("Selection: 1"); status.addPermanentWidget(self.cell_status); status.addPermanentWidget(self.selection_status); self.setStatusBar(status)

    def _view(self, index):
        view=QTableView(); model=SpreadsheetTableModel(self.workbook.sheets[index], evaluator=self._evaluate); view.setModel(model)
        view.setAlternatingRowColors(True); view.setSelectionMode(QTableView.SelectionMode.ContiguousSelection); view.horizontalHeader().setDefaultSectionSize(105); view.verticalHeader().setDefaultSectionSize(23)
        view.selectionModel().currentChanged.connect(self._selected); view.selectionModel().selectionChanged.connect(self._selection); model.cell_edited.connect(self._edited); return view

    def _tabs(self):
        self.tabs.blockSignals(True); self.tabs.clear()
        for i,sheet in enumerate(self.workbook.sheets): self.tabs.addTab(self._view(i),sheet.name)
        self.tabs.setCurrentIndex(self.workbook.active_sheet_index); self.tabs.blockSignals(False)

    def _evaluate(self, sheet, _address, formula):
        def resolve(ref):
            cell=sheet.cells.get(ref.replace("$","").upper()); return cell.value if cell else None
        return self.engine.evaluate(formula,{"get_cell_value":resolve})

    def _current(self):
        widget=self.tabs.currentWidget(); return widget if isinstance(widget,QTableView) else None

    def _selected(self,current,_previous):
        if not current.isValid(): return
        address=CellAddress(current.row(),current.column()).a1(False); self.name_box.setText(address); self.cell_status.setText(f"Cell: {address}")
        value=current.model().data(current,Qt.ItemDataRole.EditRole); self.formula_bar.setText("" if value is None else str(value))

    def _selection(self,*_):
        view=self._current(); self.selection_status.setText(f"Selection: {len(view.selectionModel().selectedIndexes()) if view else 0}")

    def _edited(self,*_): self._mark_dirty()
    def _mark_dirty(self): self.dirty=True; self._title()
    def _tab_changed(self,index):
        if index>=0:self.workbook.active_sheet_index=index

    def _apply_formula(self):
        view=self._current()
        if view and view.currentIndex().isValid(): view.model().setData(view.currentIndex(),self.formula_bar.text())

    def _go(self):
        try: address=CellAddress.parse(self.name_box.text())
        except ValueError: self.statusBar().showMessage("Invalid cell address",2500); return
        view=self._current()
        if view:
            index=view.model().index(address.row,address.column); view.setCurrentIndex(index); view.scrollTo(index)

    def _new(self):
        self.workbook=Workbook(name="Untitled"); self.workbook.add_sheet("Sheet1"); self.current_file_path=None; self.dirty=False; self._tabs(); self._title()

    def _open(self):
        path,_=QFileDialog.getOpenFileName(self,"Open workbook","","AI Workbook (*.json)")
        if not path:return
        try:self.workbook=self.storage.load_workbook(path)
        except OSError as exc: QMessageBox.warning(self,"Open failed",str(exc)); return
        self.current_file_path=path; self.dirty=False; self._tabs(); self._title()

    def _save(self):
        if not self.current_file_path:self._save_as(); return
        self.storage.save_workbook(self.current_file_path,self.workbook); self.dirty=False; self._title()

    def _save_as(self):
        path,_=QFileDialog.getSaveFileName(self,"Save workbook","","AI Workbook (*.json)")
        if path:self.current_file_path=path if path.endswith(".json") else path+".json"; self._save()

    def _import(self,kind):
        pattern="Excel Workbook (*.xlsx)" if kind=="xlsx" else "CSV File (*.csv)"; path,_=QFileDialog.getOpenFileName(self,"Import","",pattern)
        if not path:return
        try:self.workbook=(self.converter.import_xlsx(path) if kind=="xlsx" else self.converter.import_csv(path))
        except WorkbookConversionError as exc: QMessageBox.warning(self,"Import failed",str(exc)); return
        self.current_file_path=None; self.dirty=True; self._tabs(); self._title()

    def _export(self,kind):
        suffix=".xlsx" if kind=="xlsx" else ".csv"; pattern="Excel Workbook (*.xlsx)" if kind=="xlsx" else "CSV File (*.csv)"; path,_=QFileDialog.getSaveFileName(self,"Export","",pattern)
        if not path:return
        path=path if path.endswith(suffix) else path+suffix
        try:
            if kind=="xlsx":self.converter.export_xlsx(path,self.workbook)
            else:self.converter.export_csv(path,self.workbook,self.workbook.active_sheet_index)
        except WorkbookConversionError as exc: QMessageBox.warning(self,"Export failed",str(exc))

    def _add_sheet(self):
        name,ok=QInputDialog.getText(self,"Add sheet","Sheet name:",text=f"Sheet{len(self.workbook.sheets)+1}")
        if ok:self.workbook.add_sheet(self._unique(name.strip() or "Sheet")); self._mark_dirty(); self._tabs(); self.tabs.setCurrentIndex(len(self.workbook.sheets)-1)

    def _rename_sheet(self):
        i=self.tabs.currentIndex()
        if i<0:return
        name,ok=QInputDialog.getText(self,"Rename sheet","Sheet name:",text=self.workbook.sheets[i].name)
        if ok and name.strip():self.workbook.sheets[i].name=self._unique(name.strip(),i); self.tabs.setTabText(i,self.workbook.sheets[i].name); self._mark_dirty()

    def _delete_sheet(self):
        i=self.tabs.currentIndex()
        if i>=0 and len(self.workbook.sheets)>1:del self.workbook.sheets[i]; self.workbook.active_sheet_index=max(0,i-1); self._mark_dirty(); self._tabs()

    def _copy(self):
        view=self._current(); indexes=view.selectionModel().selectedIndexes() if view else []
        if not indexes:return
        rows,cols=sorted({i.row() for i in indexes}),sorted({i.column() for i in indexes}); QApplication.clipboard().setText("\n".join("\t".join(str(view.model().data(view.model().index(r,c)) or "") for c in cols) for r in rows))

    def _paste(self):
        view=self._current()
        if not view or not view.currentIndex().isValid():return
        start=view.currentIndex()
        for ro,row in enumerate(QApplication.clipboard().text().splitlines()):
            for co,value in enumerate(row.split("\t")):view.model().setData(view.model().index(start.row()+ro,start.column()+co),value)

    def _unique(self,base,exclude=None):
        names={s.name for i,s in enumerate(self.workbook.sheets) if i!=exclude}; n=2
        if base not in names:return base
        while f"{base} ({n})" in names:n+=1
        return f"{base} ({n})"

    def _title(self):
        label=Path(self.current_file_path).name if self.current_file_path else self.workbook.name; self.setWindowTitle(f"{'*' if self.dirty else ''}AI Spreadsheet — {label}")
