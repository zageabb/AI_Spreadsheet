"""Context Studio-styled desktop shell with a virtual spreadsheet grid."""
from __future__ import annotations

import os
from pathlib import Path
from PySide6.QtCore import QObject, QSettings, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QColor, QKeySequence, QUndoStack
from PySide6.QtWidgets import (QApplication, QColorDialog, QComboBox, QFileDialog,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QStatusBar, QTabWidget, QTableView, QToolBar, QVBoxLayout, QWidget)

from app.core.coordinates import CellAddress
from app.auth.service import SessionPrincipal
from app.engine.formula_engine import FormulaEngine
from app.engine.calculation_service import WorkbookCalculationService
from app.engine.plugin_loader import PluginLoader
from app.formulas.registry import register_builtin_functions
from app.models.sheet import Worksheet
from app.models.workbook import Workbook
from app.permissions.service import PermissionService
from app.services.file_conversion import WorkbookConversionError, WorkbookFileConverter
from app.services.collaboration_client import (CollaborationConflict,
    CollaborationIdentity, PresencePayload, RealtimeCollaborationClient)
from app.services.data_connectors import DataConnectorError, DataConnectorService, DataSourceSpec
from app.services.transformations import (TransformationPipeline, rows_to_worksheet,
    worksheet_to_rows)
from app.services.recovery import RecoveryManager, autosave_enabled, autosave_interval_seconds
from app.services.ai_assistant import (
    AICellContext, AISelectionContext, AISettings, SpreadsheetAIAssistant,
    build_selection_context,
)
from app.services.worksheet_editing import (
    CellRange, apply_format, clear_cells, delete_columns, delete_rows,
    insert_columns, insert_rows, replace_text, snapshot, sort_rows,
)
from app.storage import get_workbook_storage
from app.storage.postgres_storage import PostgresStorageError, PostgresWorkbookStorage
from app.ui.spreadsheet_model import SpreadsheetTableModel
from app.ui.theme import CONTEXT_STUDIO_QSS
from app.ui.transformation_dialog import TransformationDialog
from app.ui.sharing_dialog import SharingDialog
from app.ui.custom_function_dialog import CustomFunctionDialog
from app.ui.ai_assistant_dock import AIAssistantDock
from app.ui.find_replace_dialog import FindReplaceDialog
from app.ui.undo_commands import WorkbookMetadataCommand, WorksheetStateCommand
from app.ui.excel_features_dialogs import ChartDialog, ConditionalFormatDialog, NamedRangesDialog


class CollaborationBridge(QObject):
    event_received = Signal(object)


class MainWindow(QMainWindow):
    def __init__(self, principal: SessionPrincipal | None = None,
                 session_token: str | None = None) -> None:
        super().__init__()
        self.principal = principal
        self.session_token = session_token
        self.permission_service = PermissionService()
        self.collaboration: RealtimeCollaborationClient | None = None
        self.collaboration_lock: tuple[str, str] | None = None
        self.collaboration_participants: dict[str, dict] = {}
        self.collaboration_bridge = CollaborationBridge()
        self.collaboration_bridge.event_received.connect(self._collaboration_event)
        self.resize(1400, 860); self.setStyleSheet(CONTEXT_STUDIO_QSS)
        self.storage, self.converter = get_workbook_storage(), WorkbookFileConverter()
        self.connectors = DataConnectorService()
        self.recovery = RecoveryManager()
        self.engine = FormulaEngine(); register_builtin_functions(self.engine); PluginLoader().load(self.engine)
        self.workbook = self._owned_workbook("Untitled"); self.workbook.add_sheet("Sheet1")
        self.calculation = WorkbookCalculationService(self.workbook, self.engine)
        self.current_file_path: str | None = None; self.dirty = False; self.access_role = "owner"
        self.last_recovery_path: Path | None = None
        self.undo_stack=QUndoStack(self); self._pending_edit_state=None; self.find_dialog=None
        self._actions(); self._chrome(); self._create_ai_dock(); self._tabs(); self._title(); self._start_autosave()
        QTimer.singleShot(0,self._offer_recovery)

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
        self.undo_a=self.undo_stack.createUndoAction(self,"Undo"); self.undo_a.setShortcut(QKeySequence.StandardKey.Undo)
        self.redo_a=self.undo_stack.createRedoAction(self,"Redo"); self.redo_a.setShortcut(QKeySequence.StandardKey.Redo)
        self.find_a=self._make_action("Find and Replace",QKeySequence.StandardKey.Find,self._show_find_replace)
        self.clear_a=self._make_action("Clear Cells",QKeySequence.StandardKey.Delete,self._clear_selection)
        self.edit_cell_a=self._make_action("Edit Cell","F2",self._edit_current_cell)
        self.first_cell_a=self._make_action("Go to A1","Ctrl+Home",lambda:self._navigate_to(False))
        self.last_cell_a=self._make_action("Go to Last Used Cell","Ctrl+End",lambda:self._navigate_to(True))
        self.insert_rows_a=self._make_action("Insert Rows",None,lambda:self._change_rows(True))
        self.delete_rows_a=self._make_action("Delete Rows",None,lambda:self._change_rows(False))
        self.insert_columns_a=self._make_action("Insert Columns",None,lambda:self._change_columns(True))
        self.delete_columns_a=self._make_action("Delete Columns",None,lambda:self._change_columns(False))
        self.sort_asc_a=self._make_action("Sort Ascending",None,lambda:self._sort_selection(False))
        self.sort_desc_a=self._make_action("Sort Descending",None,lambda:self._sort_selection(True))
        self.filter_a=self._make_action("Filter Current Column",None,self._filter_current_column)
        self.clear_filter_a=self._make_action("Clear Row Filter",None,self._clear_row_filter)
        self.bold_a=self._make_action("Bold","Ctrl+B",lambda:self._toggle_format("bold")); self.bold_a.setCheckable(True)
        self.italic_a=self._make_action("Italic","Ctrl+I",lambda:self._toggle_format("italic")); self.italic_a.setCheckable(True)
        self.underline_a=self._make_action("Underline","Ctrl+U",lambda:self._toggle_format("underline")); self.underline_a.setCheckable(True)
        self.fill_a=self._make_action("Fill Colour",None,lambda:self._choose_colour("fill_color"))
        self.font_colour_a=self._make_action("Font Colour",None,lambda:self._choose_colour("font_color"))
        self.conditional_format_a=self._make_action("Conditional Formatting",None,self._conditional_format)
        self.clear_conditional_a=self._make_action("Clear Conditional Formatting",None,self._clear_conditional_formats)
        self.named_ranges_a=self._make_action("Named Ranges","Ctrl+F3",self._named_ranges)
        self.chart_a=self._make_action("Create Chart","Alt+F1",self._create_chart)
        self.transform_a=self._make_action("Transform Data","Ctrl+Shift+T",self._transform_data)
        self.connect_csv_a=self._make_action("Connect CSV",None,self._connect_csv)
        self.connect_sqlite_a=self._make_action("Connect SQLite",None,self._connect_sqlite)
        self.refresh_data_a=self._make_action("Refresh Data","Ctrl+Alt+R",self._refresh_data)
        self.share_a=self._make_action("Share Workbook",None,self._share_workbook)
        self.custom_functions_a=self._make_action("Custom Python Functions",None,self._custom_functions)
        self.ai_a=self._make_action("AI Assistant","Ctrl+Shift+A",lambda:self.ai_dock.setVisible(not self.ai_dock.isVisible()))
        self.ai_a.setCheckable(True); self.ai_a.setChecked(True)
        self.sign_out_a=self._make_action("Sign Out",None,self.close)

    def _chrome(self):
        file_menu=self.menuBar().addMenu("File"); file_menu.addActions([self.new_a,self.open_a]); self.recent_menu=file_menu.addMenu("Open Recent"); self._refresh_recent_menu(); file_menu.addActions([self.save_a,self.saveas_a,self.xlsx_in,self.csv_in,self.xlsx_out,self.csv_out]); file_menu.addSeparator(); file_menu.addAction(self.sign_out_a)
        edit_menu=self.menuBar().addMenu("Edit"); edit_menu.addActions([self.undo_a,self.redo_a]); edit_menu.addSeparator(); edit_menu.addActions([self.copy_a,self.paste_a,self.clear_a,self.find_a,self.edit_cell_a]); edit_menu.addSeparator(); edit_menu.addActions([self.first_cell_a,self.last_cell_a])
        format_menu=self.menuBar().addMenu("Format"); format_menu.addActions([self.bold_a,self.italic_a,self.underline_a,self.fill_a,self.font_colour_a]); format_menu.addSeparator(); format_menu.addActions([self.conditional_format_a,self.clear_conditional_a])
        sheet_menu=self.menuBar().addMenu("Sheet"); sheet_menu.addActions([self.add_a,self.rename_a,self.delete_a]); sheet_menu.addSeparator(); sheet_menu.addActions([self.insert_rows_a,self.delete_rows_a,self.insert_columns_a,self.delete_columns_a])
        data_menu=self.menuBar().addMenu("Data"); data_menu.addActions([self.sort_asc_a,self.sort_desc_a,self.filter_a,self.clear_filter_a]); data_menu.addSeparator(); data_menu.addActions([self.named_ranges_a,self.chart_a]); data_menu.addSeparator(); data_menu.addActions([self.connect_csv_a,self.connect_sqlite_a,self.refresh_data_a]); data_menu.addSeparator(); data_menu.addAction(self.transform_a)
        access_menu=self.menuBar().addMenu("Access"); access_menu.addAction(self.share_a)
        tools_menu=self.menuBar().addMenu("Tools"); tools_menu.addActions([self.ai_a,self.custom_functions_a])
        bar=QToolBar("Workbook"); bar.setMovable(False); bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        bar.addActions([self.new_a,self.open_a,self.save_a]); bar.addSeparator(); bar.addActions([self.undo_a,self.redo_a,self.copy_a,self.paste_a]); bar.addSeparator(); bar.addActions([self.bold_a,self.italic_a,self.underline_a,self.fill_a,self.font_colour_a])
        self.number_format=QComboBox(); self.number_format.addItems(["General","Number","Currency","Percentage","Date"]); self.number_format.currentTextChanged.connect(self._number_format_changed); bar.addWidget(self.number_format)
        bar.addSeparator(); bar.addAction(self.add_a); self.addToolBar(bar)
        root=QWidget(); layout=QVBoxLayout(root); layout.setContentsMargins(10,10,10,8)
        formula=QHBoxLayout(); self.name_box=QLineEdit("A1"); self.name_box.setFixedWidth(90); self.name_box.returnPressed.connect(self._go)
        self.formula_bar=QLineEdit(); self.formula_bar.setPlaceholderText("Enter a value or formula"); self.formula_bar.returnPressed.connect(self._apply_formula)
        formula.addWidget(self.name_box); formula.addWidget(QLabel("fx")); formula.addWidget(self.formula_bar); layout.addLayout(formula)
        self.tabs=QTabWidget(); self.tabs.setDocumentMode(True); self.tabs.setMovable(True); self.tabs.currentChanged.connect(self._tab_changed)
        plus=QPushButton("+"); plus.clicked.connect(self._add_sheet); self.tabs.setCornerWidget(plus); layout.addWidget(self.tabs); self.setCentralWidget(root)
        status=QStatusBar(); self.cell_status=QLabel("Cell: A1"); self.selection_status=QLabel("Selection: 1"); self.autosave_status=QLabel("Recovery: ready"); self.collaboration_status=QLabel("Collaboration: local"); self.identity_status=QLabel(self._identity_label()); status.addPermanentWidget(self.autosave_status); status.addPermanentWidget(self.collaboration_status); status.addPermanentWidget(self.identity_status); status.addPermanentWidget(self.cell_status); status.addPermanentWidget(self.selection_status); self.setStatusBar(status)

    def _view(self, index):
        view=QTableView(); model=SpreadsheetTableModel(self.workbook.sheets[index], evaluator=self._evaluate, editable=self._can_edit()); view.setModel(model)
        view.setAlternatingRowColors(True); view.setSelectionMode(QTableView.SelectionMode.ContiguousSelection); view.horizontalHeader().setDefaultSectionSize(105); view.verticalHeader().setDefaultSectionSize(23)
        view.selectionModel().currentChanged.connect(self._selected); view.selectionModel().selectionChanged.connect(self._selection)
        model.cell_editing.connect(self._capture_edit_state); model.cell_edited.connect(self._edited); return view

    def _tabs(self):
        self.tabs.blockSignals(True); self.tabs.clear()
        for i,sheet in enumerate(self.workbook.sheets): self.tabs.addTab(self._view(i),sheet.name)
        self.tabs.setCurrentIndex(self.workbook.active_sheet_index); self.tabs.blockSignals(False)
        self._update_access_ui()

    def _evaluate(self, sheet, _address, formula):
        return self.calculation.evaluate_formula(sheet.name, formula)

    def _current(self):
        widget=self.tabs.currentWidget(); return widget if isinstance(widget,QTableView) else None

    def _selected(self,current,_previous):
        if not current.isValid(): return
        address=CellAddress(current.row(),current.column()).a1(False); self.name_box.setText(address); self.cell_status.setText(f"Cell: {address}")
        value=current.model().data(current,Qt.ItemDataRole.EditRole); self.formula_bar.setText("" if value is None else str(value))

    def _selection(self,*_):
        view=self._current(); indexes=view.selectionModel().selectedIndexes() if view else []
        self.selection_status.setText(f"Selection: {len(indexes)}")
        if indexes:
            top,bottom=min(i.row() for i in indexes),max(i.row() for i in indexes)
            left,right=min(i.column() for i in indexes),max(i.column() for i in indexes)
            start=CellAddress(top,left).a1(False); end=CellAddress(bottom,right).a1(False)
            self._publish_presence(start if start==end else f"{start}:{end}")

    def _capture_edit_state(self,state):
        self._pending_edit_state=state

    def _edited(self,address,*_):
        sheet=self.workbook.get_active_sheet()
        self.calculation.recalculate({self.calculation.cell_key(sheet.name,address)})
        if self._pending_edit_state is not None:
            self.undo_stack.push(WorksheetStateCommand(
                f"Edit {address}",sheet,self._pending_edit_state,snapshot(sheet),self._refresh_after_undo
            ))
            self._pending_edit_state=None
        for index in range(self.tabs.count()):
            view=self.tabs.widget(index)
            if isinstance(view,QTableView): view.model().refresh()
        self._mark_dirty()
        if self.collaboration:
            cell=sheet.cells.get(address)
            try:self.collaboration.publish_cell_change(sheet.name,address,cell.value if cell else None,cell.formula if cell else None)
            except CollaborationConflict as exc:self.statusBar().showMessage(f"Collaboration conflict: {exc}. Your local edit was not broadcast.",6000)
            except (OSError,RuntimeError) as exc:self.statusBar().showMessage(f"Collaboration offline: {exc}",4000)

    def _refresh_after_undo(self):
        self.calculation=WorkbookCalculationService(self.workbook,self.engine); self.calculation.recalculate()
        for index in range(self.tabs.count()):
            view=self.tabs.widget(index)
            if isinstance(view,QTableView):view.model().refresh()
        self._mark_dirty()

    def _selected_range(self):
        view=self._current()
        if view is None:return None
        indexes=view.selectionModel().selectedIndexes()
        if not indexes and view.currentIndex().isValid():indexes=[view.currentIndex()]
        if not indexes:return None
        return CellRange(min(i.row() for i in indexes),min(i.column() for i in indexes),
                         max(i.row() for i in indexes),max(i.column() for i in indexes))

    def _record_operation(self,label,operation):
        if not self._can_edit():return 0
        sheet=self.workbook.get_active_sheet(); before=snapshot(sheet); result=operation(sheet)
        after=snapshot(sheet)
        if before==after:return result
        self.undo_stack.push(WorksheetStateCommand(label,sheet,before,after,self._refresh_after_undo))
        self._refresh_after_undo(); return result

    def _clear_selection(self):
        selected=self._selected_range()
        if selected:self._record_operation("Clear cells",lambda sheet:clear_cells(sheet,selected))

    def _toggle_format(self,key):
        selected=self._selected_range()
        if not selected:return
        sheet=self.workbook.get_active_sheet(); current=sheet.cells.get(next(iter(selected.addresses())))
        enabled=not bool(current and current.formatting.get(key))
        self._record_operation(f"Set {key}",lambda target:apply_format(target,selected,{key:enabled}))

    def _choose_colour(self,key):
        selected=self._selected_range()
        if not selected:return
        colour=QColorDialog.getColor(QColor("#ffffff"),self,"Choose colour")
        if colour.isValid():self._record_operation("Change colour",lambda sheet:apply_format(sheet,selected,{key:colour.name().lstrip("#")}))

    def _number_format_changed(self,label):
        if label=="General" and not self.number_format.hasFocus():return
        selected=self._selected_range()
        if not selected:return
        formats={"General":None,"Number":"0.00","Currency":"£#,##0.00","Percentage":"0.00%","Date":"dd/mm/yyyy"}
        self._record_operation("Change number format",lambda sheet:apply_format(sheet,selected,{"number_format":formats[label]}))

    def _conditional_format(self):
        selected=self._selected_range()
        if not selected:return
        range_ref=self._range_ref(selected)
        dialog=ConditionalFormatDialog(range_ref,self)
        if not dialog.exec():return
        rule=dialog.rule()
        self._record_operation("Add conditional format",lambda sheet:sheet.metadata.setdefault("conditional_formats",[]).append(rule))

    def _clear_conditional_formats(self):
        sheet=self.workbook.get_active_sheet()
        if not sheet.metadata.get("conditional_formats"):return
        answer=QMessageBox.question(self,"Clear conditional formatting","Remove all conditional-format rules from this sheet?")
        if answer==QMessageBox.StandardButton.Yes:self._record_operation("Clear conditional formats",lambda target:target.metadata.pop("conditional_formats",None))

    def _named_ranges(self):
        selected=self._selected_range(); sheet=self.workbook.get_active_sheet()
        reference=f"'{sheet.name.replace(chr(39),chr(39)*2)}'!{self._range_ref(selected)}" if selected else f"'{sheet.name}'!A1"
        before=dict(self.workbook.metadata)
        dialog=NamedRangesDialog(self.workbook.metadata.get("defined_names",[]),reference,[item.name for item in self.workbook.sheets],self)
        if not dialog.exec():return
        from copy import deepcopy
        before=deepcopy(before); self.workbook.metadata["defined_names"]=dialog.names; after=deepcopy(self.workbook.metadata)
        if before==after:return
        self.undo_stack.push(WorkbookMetadataCommand("Edit named ranges",self.workbook,before,after,self._refresh_after_undo)); self._refresh_after_undo()

    def _create_chart(self):
        selected=self._selected_range()
        if not selected or selected.bottom<=selected.top or selected.right<=selected.left:
            QMessageBox.information(self,"Create chart","Select headers plus at least one category and value column."); return
        range_ref=self._range_ref(selected); anchor=CellAddress(selected.top,selected.right+2).a1(False)
        dialog=ChartDialog(range_ref,anchor,self)
        if not dialog.exec():return
        chart=dialog.chart()
        self._record_operation("Create chart",lambda sheet:sheet.metadata.setdefault("charts",[]).append(chart))
        self.statusBar().showMessage("Chart added; export to Excel to view it",3500)

    @staticmethod
    def _range_ref(selected):
        start=CellAddress(selected.top,selected.left).a1(False); end=CellAddress(selected.bottom,selected.right).a1(False)
        return start if start==end else f"{start}:{end}"

    def _change_rows(self,inserting):
        selected=self._selected_range()
        if not selected:return
        count=selected.bottom-selected.top+1
        operation=(lambda sheet:insert_rows(sheet,selected.top,count)) if inserting else (lambda sheet:delete_rows(sheet,selected.top,count))
        self._record_operation(("Insert" if inserting else "Delete")+" rows",operation)

    def _change_columns(self,inserting):
        selected=self._selected_range()
        if not selected:return
        count=selected.right-selected.left+1
        operation=(lambda sheet:insert_columns(sheet,selected.left,count)) if inserting else (lambda sheet:delete_columns(sheet,selected.left,count))
        self._record_operation(("Insert" if inserting else "Delete")+" columns",operation)

    def _sort_selection(self,reverse):
        selected=self._selected_range(); view=self._current()
        if not selected or view is None:return
        key=view.currentIndex().column()
        if not selected.left<=key<=selected.right:key=selected.left
        self._record_operation("Sort descending" if reverse else "Sort ascending",
                               lambda sheet:sort_rows(sheet,selected,key,reverse=reverse))

    def _filter_current_column(self):
        view=self._current()
        if view is None or not view.currentIndex().isValid():return
        value,ok=QInputDialog.getText(self,"Filter current column","Show rows containing:")
        if not ok:return
        column=view.currentIndex().column(); needle=value.casefold()
        sheet=self.workbook.get_active_sheet()
        used=max((CellAddress.parse(address).row for address in sheet.cells),default=-1)
        for row in range(used+1):
            cell=sheet.cells.get(CellAddress(row,column).a1(False))
            content=cell.formula if cell and cell.formula is not None else cell.value if cell else ""
            view.setRowHidden(row,needle not in str(content).casefold())
        self.statusBar().showMessage(f"Filtered column {CellAddress(0,column).a1(False)[:-1]}",2500)

    def _clear_row_filter(self):
        view=self._current()
        if view is None:return
        sheet=self.workbook.get_active_sheet(); used=max((CellAddress.parse(address).row for address in sheet.cells),default=-1)
        for row in range(used+1):view.setRowHidden(row,False)

    def _show_find_replace(self):
        if self.find_dialog is None:
            self.find_dialog=FindReplaceDialog(self)
            self.find_dialog.find_next.connect(self._find_next)
            self.find_dialog.replace_one.connect(self._replace_one)
            self.find_dialog.replace_all.connect(self._replace_all)
        self.find_dialog.show(); self.find_dialog.raise_(); self.find_dialog.focus_find()

    def _matching_indexes(self,text,match_case):
        if not text:return []
        sheet=self.workbook.get_active_sheet(); needle=text if match_case else text.casefold(); matches=[]
        for address,cell in sheet.cells.items():
            content=cell.formula if cell.formula is not None else cell.value
            haystack=str(content) if match_case else str(content).casefold()
            if needle in haystack:matches.append(CellAddress.parse(address))
        return sorted(matches,key=lambda item:(item.row,item.column))

    def _find_next(self,text,match_case):
        matches=self._matching_indexes(text,match_case); view=self._current()
        if not matches or view is None:
            self.statusBar().showMessage("No matching cells",2500); return
        current=view.currentIndex(); position=(current.row(),current.column()) if current.isValid() else (-1,-1)
        target=next((item for item in matches if (item.row,item.column)>position),matches[0])
        index=view.model().index(target.row,target.column); view.setCurrentIndex(index); view.scrollTo(index)

    def _replace_one(self,find,replacement,match_case):
        view=self._current()
        if view is None or not view.currentIndex().isValid():return
        index=view.currentIndex(); selected=CellRange(index.row(),index.column(),index.row(),index.column())
        changed=self._record_operation("Replace cell",lambda sheet:replace_text(sheet,find,replacement,match_case=match_case,cell_range=selected))
        if changed:self._find_next(find,match_case)

    def _replace_all(self,find,replacement,match_case):
        changed=self._record_operation("Replace all",lambda sheet:replace_text(sheet,find,replacement,match_case=match_case))
        self.statusBar().showMessage(f"Replaced {changed} cell(s)",3000)
    def _mark_dirty(self): self.dirty=True; self._title()
    def _tab_changed(self,index):
        if index>=0:
            self.workbook.active_sheet_index=index
            self._publish_presence(None)

    def _apply_formula(self):
        view=self._current()
        if view and view.currentIndex().isValid(): view.model().setData(view.currentIndex(),self.formula_bar.text())

    def _go(self):
        try: address=CellAddress.parse(self.name_box.text())
        except ValueError: self.statusBar().showMessage("Invalid cell address",2500); return
        view=self._current()
        if view:
            index=view.model().index(address.row,address.column); view.setCurrentIndex(index); view.scrollTo(index)

    def _edit_current_cell(self):
        view=self._current()
        if view and view.currentIndex().isValid() and self._can_edit():view.edit(view.currentIndex())

    def _navigate_to(self,last):
        view=self._current()
        if view is None:return
        if last:
            addresses=[CellAddress.parse(address) for address in self.workbook.get_active_sheet().cells]
            row=max((item.row for item in addresses),default=0); column=max((item.column for item in addresses),default=0)
        else:row=column=0
        index=view.model().index(row,column); view.setCurrentIndex(index); view.scrollTo(index)

    def _new(self):
        if not self._confirm_replace():return
        self._stop_collaboration(); self.undo_stack.clear(); self.workbook=self._owned_workbook("Untitled"); self.workbook.add_sheet("Sheet1"); self.access_role="owner"; self.calculation=WorkbookCalculationService(self.workbook,self.engine); self.current_file_path=None; self.dirty=False; self._tabs(); self._title()

    def _open(self):
        if isinstance(self.storage,PostgresWorkbookStorage):
            path,ok=QInputDialog.getText(self,"Open PostgreSQL workbook","Workbook key:")
            if not ok:path=""
        else:path,_=QFileDialog.getOpenFileName(self,"Open workbook","","AI Workbook (*.json)")
        if not path:return
        if not self._confirm_replace():return
        try:
            if isinstance(self.storage,PostgresWorkbookStorage) and self.principal:
                workbook=self.storage.load_workbook_for_user(path,self.principal.email)
            else:workbook=self.storage.load_workbook(path)
        except (OSError,PostgresStorageError) as exc: QMessageBox.warning(self,"Open failed",str(exc)); return
        role,claimed=self.permission_service.resolve_or_claim(self.principal.email,workbook) if self.principal else ("owner",False)
        if role is None:QMessageBox.warning(self,"Access denied","You do not have access to this workbook."); return
        self.undo_stack.clear(); self.workbook=workbook; self.access_role=role
        self.calculation=WorkbookCalculationService(self.workbook,self.engine); self.calculation.recalculate(); self.current_file_path=path; self.dirty=claimed; self._tabs(); self._title()
        if claimed:self.statusBar().showMessage("This legacy workbook is now assigned to you; save it to persist ownership.",5000)
        self._start_collaboration()
        self._remember_recent(path)

    def _save(self):
        if not self._can_edit():QMessageBox.warning(self,"Read only","Viewers cannot save changes to this workbook."); return False
        if not self.current_file_path:return self._save_as()
        try:
            if isinstance(self.storage,PostgresWorkbookStorage) and self.principal:
                self.storage.save_workbook_for_user(self.current_file_path,self.workbook,self.principal.email)
            else:self.storage.save_workbook(self.current_file_path,self.workbook)
        except (OSError,PostgresStorageError) as exc:QMessageBox.warning(self,"Save failed",str(exc)); return False
        self.dirty=False; self._title()
        self.recovery.discard_for(self.workbook,self.current_file_path,self._recovery_identity())
        if self.last_recovery_path:self.recovery.discard(self.last_recovery_path); self.last_recovery_path=None
        self._remember_recent(self.current_file_path)
        self._start_collaboration()
        return True

    def _save_as(self):
        if not self._can_edit():return False
        if isinstance(self.storage,PostgresWorkbookStorage):
            path,ok=QInputDialog.getText(self,"Save PostgreSQL workbook","Workbook key:",text=self.current_file_path or "")
            if not ok:path=""
            if path:self.current_file_path=path.strip(); return self._save()
        else:
            path,_=QFileDialog.getSaveFileName(self,"Save workbook","","AI Workbook (*.json)")
            if path:self.current_file_path=path if path.endswith(".json") else path+".json"; return self._save()
        return False

    def _import(self,kind):
        pattern="Excel Workbook (*.xlsx)" if kind=="xlsx" else "CSV File (*.csv)"; path,_=QFileDialog.getOpenFileName(self,"Import","",pattern)
        if not path:return
        if not self._confirm_replace():return
        try:self.workbook=(self.converter.import_xlsx(path) if kind=="xlsx" else self.converter.import_csv(path))
        except WorkbookConversionError as exc: QMessageBox.warning(self,"Import failed",str(exc)); return
        if self.principal:self.workbook.permissions=self.permission_service.assign_owner(self.workbook.permissions,self.principal.email)
        self.undo_stack.clear(); self.access_role="owner"; self.calculation=WorkbookCalculationService(self.workbook,self.engine); self.calculation.recalculate(); self.current_file_path=None; self.dirty=True; self._tabs(); self._title()

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
        self.undo_stack.beginMacro("Paste cells")
        try:
            for ro,row in enumerate(QApplication.clipboard().text().splitlines()):
                for co,value in enumerate(row.split("\t")):view.model().setData(view.model().index(start.row()+ro,start.column()+co),value)
        finally:self.undo_stack.endMacro()

    def _transform_data(self):
        sheet=self.workbook.get_active_sheet(); rows=worksheet_to_rows(sheet)
        if not rows:
            QMessageBox.information(self,"Transform Data","The active sheet needs a header row and at least one data row."); return
        dialog=TransformationDialog(rows,self)
        if not dialog.exec():return
        rows_to_worksheet(dialog.result_rows,sheet)
        sheet.metadata["transformations"]=[step.to_dict() for step in dialog.steps]
        self.calculation=WorkbookCalculationService(self.workbook,self.engine); self.calculation.recalculate()
        self._mark_dirty(); self._tabs(); self.statusBar().showMessage(f"Applied {len(dialog.steps)} transformation step(s)",3000)

    def _connect_csv(self):
        path,_=QFileDialog.getOpenFileName(self,"Connect CSV","","CSV File (*.csv)")
        if not path:return
        self._load_source(DataSourceSpec("csv",path,{"encoding":"utf-8-sig","delimiter":","}))

    def _connect_sqlite(self):
        path,_=QFileDialog.getOpenFileName(self,"Connect SQLite","","SQLite Database (*.sqlite *.sqlite3 *.db);;All Files (*)")
        if not path:return
        try:tables=self.connectors.list_sqlite_tables(path)
        except DataConnectorError as exc:QMessageBox.warning(self,"SQLite connection failed",str(exc)); return
        if not tables:QMessageBox.information(self,"Connect SQLite","No user tables were found."); return
        table,ok=QInputDialog.getItem(self,"Connect SQLite","Table:",tables,0,False)
        if ok:self._load_source(DataSourceSpec("sqlite",path,{"table":table,"limit":100000}))

    def _load_source(self,source):
        try:rows=self.connectors.load(source)
        except DataConnectorError as exc:QMessageBox.warning(self,"Data connection failed",str(exc)); return
        sheet=self.workbook.get_active_sheet(); rows_to_worksheet(rows,sheet)
        sheet.metadata["data_source"]=source.to_dict(); sheet.metadata["transformations"]=[]
        self.calculation=WorkbookCalculationService(self.workbook,self.engine); self.calculation.recalculate()
        self._mark_dirty(); self._tabs(); self.statusBar().showMessage(f"Loaded {len(rows):,} rows",3000)

    def _refresh_data(self):
        sheet=self.workbook.get_active_sheet(); payload=sheet.metadata.get("data_source")
        if not isinstance(payload,dict):QMessageBox.information(self,"Refresh Data","The active sheet has no refreshable data source."); return
        try:
            source=DataSourceSpec.from_dict(payload); rows=self.connectors.load(source)
            steps=sheet.metadata.get("transformations",[])
            result=TransformationPipeline.from_dicts(steps).apply(rows)
        except (DataConnectorError,KeyError,TypeError,ValueError) as exc:QMessageBox.warning(self,"Refresh failed",str(exc)); return
        rows_to_worksheet(result,sheet); self.calculation=WorkbookCalculationService(self.workbook,self.engine); self.calculation.recalculate()
        self._mark_dirty(); self._tabs(); self.statusBar().showMessage(f"Refreshed {len(result):,} rows from {len(rows):,} source rows",3500)

    def _unique(self,base,exclude=None):
        names={s.name for i,s in enumerate(self.workbook.sheets) if i!=exclude}; n=2
        if base not in names:return base
        while f"{base} ({n})" in names:n+=1
        return f"{base} ({n})"

    def _title(self):
        if self.current_file_path:
            label=(f"PostgreSQL · {self.current_file_path}" if isinstance(self.storage,PostgresWorkbookStorage) else Path(self.current_file_path).name)
        else:label=self.workbook.name
        self.setWindowTitle(f"{'*' if self.dirty else ''}AI Spreadsheet — {label}")

    def _owned_workbook(self,name):
        if self.principal:return self.permission_service.create_workbook_with_owner(name,self.principal.email)
        return Workbook(name=name)

    def _resolve_access(self,workbook):
        if not self.principal:return "owner"
        role,_claimed=self.permission_service.resolve_or_claim(self.principal.email,workbook)
        return role

    def _can_edit(self):return self.access_role in {"owner","editor"}

    def _identity_label(self):
        email=self.principal.email if self.principal else "Local session"
        return f"{email} · {getattr(self,'access_role','owner')}"

    def _update_access_ui(self):
        editable=self._can_edit()
        for action in [self.save_a,self.saveas_a,self.add_a,self.rename_a,self.delete_a,self.paste_a,self.clear_a,
                       self.insert_rows_a,self.delete_rows_a,self.insert_columns_a,self.delete_columns_a,
                       self.sort_asc_a,self.sort_desc_a,self.bold_a,self.italic_a,self.underline_a,self.fill_a,
                       self.font_colour_a,self.conditional_format_a,self.clear_conditional_a,self.named_ranges_a,self.chart_a,
                       self.transform_a,self.connect_csv_a,self.connect_sqlite_a,self.refresh_data_a]:action.setEnabled(editable)
        self.undo_a.setEnabled(editable and self.undo_stack.canUndo()); self.redo_a.setEnabled(editable and self.undo_stack.canRedo())
        self.share_a.setEnabled(self.access_role=="owner")
        self.formula_bar.setReadOnly(not editable)
        corner=self.tabs.cornerWidget()
        if corner:corner.setEnabled(editable)
        if hasattr(self,"identity_status"):self.identity_status.setText(self._identity_label())

    def _share_workbook(self):
        if not self.principal or self.access_role!="owner":return
        dialog=SharingDialog(
            self.workbook,self.principal.email,self.permission_service,parent=self
        )
        dialog.exec()
        if dialog.changed:
            self.access_role=self._resolve_access(self.workbook) or "viewer"
            self._mark_dirty(); self._tabs()

    def _custom_functions(self):
        dialog=CustomFunctionDialog(self.engine,parent=self)
        if dialog.exec() and dialog.saved_functions:
            self.calculation.recalculate()
            for index in range(self.tabs.count()):
                view=self.tabs.widget(index)
                if isinstance(view,QTableView):view.model().refresh()
            self.statusBar().showMessage(
                f"Registered custom functions: {', '.join(dialog.saved_functions)}",5000
            )

    def _create_ai_dock(self):
        try:settings=AISettings.from_env()
        except ValueError as exc:
            settings=AISettings(False,"ollama","http://127.0.0.1:11434","disabled","",60,200,50)
            self.statusBar().showMessage(f"AI configuration error: {exc}",6000)
        self.ai_dock=AIAssistantDock(
            context_provider=self._ai_selection_context,
            assistant=SpreadsheetAIAssistant(settings=settings),parent=self,
        )
        self.ai_dock.apply_requested.connect(self._apply_ai_proposals)
        self.ai_dock.visibilityChanged.connect(self.ai_a.setChecked)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,self.ai_dock)

    def _ai_selection_context(self):
        view=self._current()
        if view is None:raise RuntimeError("Open a worksheet before asking the AI assistant.")
        settings=self.ai_dock.assistant.settings
        ranges=list(view.selectionModel().selection())
        if not ranges and view.currentIndex().isValid():
            index=view.currentIndex(); bounds=(index.row(),index.column(),index.row(),index.column())
        elif ranges:
            bounds=(min(item.top() for item in ranges),min(item.left() for item in ranges),
                    max(item.bottom() for item in ranges),max(item.right() for item in ranges))
        else:raise RuntimeError("Select one or more cells first.")
        start=CellAddress(bounds[0],bounds[1]).a1(False); end=CellAddress(bounds[2],bounds[3]).a1(False)
        sheet=self.workbook.get_active_sheet(); cells=[]
        if not ranges:
            address=start; cell=sheet.cells.get(address)
            cells.append(AICellContext(address,cell.value if cell else None,cell.formula if cell else None))
        for selected in ranges:
            for row in range(selected.top(),selected.bottom()+1):
                for column in range(selected.left(),selected.right()+1):
                    address=CellAddress(row,column).a1(False); cell=sheet.cells.get(address)
                    cells.append(AICellContext(address,cell.value if cell else None,cell.formula if cell else None))
                    if len(cells)>settings.max_context_cells:break
                if len(cells)>settings.max_context_cells:break
            if len(cells)>settings.max_context_cells:break
        return build_selection_context(
            self.workbook.name,sheet.name,start if start==end else f"{start}:{end}",
            cells,settings.max_context_cells,
        )

    def _apply_ai_proposals(self,proposals):
        if not self._can_edit():
            QMessageBox.warning(self,"Read only","AI proposals cannot be applied to a read-only workbook."); return
        answer=QMessageBox.question(
            self,"Apply AI proposals",
            f"Apply {len(proposals)} proposed cell change(s)? Review the proposal list before continuing.",
        )
        if answer!=QMessageBox.StandardButton.Yes:return
        sheet=self.workbook.get_active_sheet(); before=snapshot(sheet); changed=set()
        for proposal in proposals:
            sheet=next((item for item in self.workbook.sheets if item.name==proposal.sheet_name),None)
            if sheet is None:continue
            cell=sheet.get_cell(proposal.address); cell.formula=proposal.formula
            cell.value=None if proposal.formula is not None else proposal.value
            changed.add(self.calculation.cell_key(sheet.name,proposal.address))
        self.calculation.recalculate(changed); self._mark_dirty()
        self.undo_stack.push(WorksheetStateCommand("Apply AI proposals",sheet,before,snapshot(sheet),self._refresh_after_undo))
        for index in range(self.tabs.count()):
            view=self.tabs.widget(index)
            if isinstance(view,QTableView):view.model().refresh()
        self.ai_dock.mark_proposals_applied()
        self.statusBar().showMessage(f"Applied {len(changed)} approved AI proposal(s)",4000)

    def _start_autosave(self):
        self.autosave_timer=QTimer(self)
        try:
            enabled=autosave_enabled(); interval=autosave_interval_seconds()
        except ValueError as exc:
            self.autosave_status.setText("Recovery: config error")
            self.statusBar().showMessage(str(exc),5000); return
        if not enabled:
            self.autosave_status.setText("Recovery: off"); return
        self.autosave_timer.timeout.connect(self._autosave)
        self.autosave_timer.start(interval*1000)

    def _autosave(self):
        if not self.dirty or not self._can_edit():return
        try:self.last_recovery_path=self.recovery.snapshot(self.workbook,self.current_file_path,self._recovery_identity())
        except (OSError,ValueError) as exc:
            self.autosave_status.setText("Recovery: failed")
            self.statusBar().showMessage(f"Recovery snapshot failed: {exc}",4000); return
        self.autosave_status.setText("Recovery: saved")

    def _offer_recovery(self):
        candidates=self.recovery.candidates(self._recovery_identity())
        if not candidates:return
        candidate=candidates[0]
        answer=QMessageBox.question(
            self,"Recover unsaved workbook",
            f"An autosave for '{candidate.workbook_name}' is available from {candidate.saved_at}. Recover it now?",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
        )
        if answer!=QMessageBox.StandardButton.Yes:return
        try:workbook=self.recovery.restore(candidate)
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,"Recovery failed",str(exc)); return
        role,_=self.permission_service.resolve_or_claim(self.principal.email,workbook) if self.principal else ("owner",False)
        if role is None:
            QMessageBox.warning(self,"Recovery denied","Your account cannot access this recovered workbook."); return
        self.undo_stack.clear(); self.workbook=workbook; self.access_role=role; self.current_file_path=candidate.source_path
        self.last_recovery_path=candidate.path
        self.calculation=WorkbookCalculationService(self.workbook,self.engine); self.calculation.recalculate()
        self.dirty=True; self._tabs(); self._title(); self.autosave_status.setText("Recovery: restored")

    def _recovery_identity(self):
        return self.principal.email if self.principal else "local"

    def _recent_paths(self):
        value=QSettings("AI Spreadsheet","AI Spreadsheet").value("recent_files",[])
        return [str(item) for item in (value if isinstance(value,list) else [value]) if item]

    def _remember_recent(self,path):
        if isinstance(self.storage,PostgresWorkbookStorage):return
        paths=[str(Path(path))]+[item for item in self._recent_paths() if item!=str(Path(path))]
        QSettings("AI Spreadsheet","AI Spreadsheet").setValue("recent_files",paths[:8])
        self._refresh_recent_menu()

    def _refresh_recent_menu(self):
        if not hasattr(self,"recent_menu"):return
        self.recent_menu.clear(); paths=self._recent_paths()
        if not paths:
            action=self.recent_menu.addAction("No recent workbooks"); action.setEnabled(False); return
        for path in paths:
            action=self.recent_menu.addAction(Path(path).name)
            action.setToolTip(path); action.triggered.connect(lambda _checked=False,p=path:self._open_recent(p))

    def _open_recent(self,path):
        if not Path(path).exists():
            QMessageBox.warning(self,"Open Recent","The workbook no longer exists."); return
        if not self._confirm_replace():return
        try:workbook=self.storage.load_workbook(path)
        except (OSError,ValueError) as exc:QMessageBox.warning(self,"Open failed",str(exc)); return
        role,_=self.permission_service.resolve_or_claim(self.principal.email,workbook) if self.principal else ("owner",False)
        if role is None:QMessageBox.warning(self,"Access denied","You do not have access to this workbook."); return
        self.undo_stack.clear(); self.workbook=workbook; self.access_role=role; self.current_file_path=path
        self.calculation=WorkbookCalculationService(self.workbook,self.engine); self.calculation.recalculate()
        self.dirty=False; self._tabs(); self._title(); self._remember_recent(path); self._start_collaboration()

    def _confirm_replace(self):
        if not self.dirty:return True
        answer=QMessageBox.question(
            self,"Unsaved changes","Save changes before replacing the current workbook?",
            QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel,
        )
        if answer==QMessageBox.StandardButton.Cancel:return False
        if answer==QMessageBox.StandardButton.Save:return bool(self._save())
        if self.last_recovery_path:self.recovery.discard(self.last_recovery_path); self.last_recovery_path=None
        return True

    def _collaboration_key(self):
        if not self.current_file_path:return None
        return self.current_file_path if isinstance(self.storage,PostgresWorkbookStorage) else Path(self.current_file_path).stem

    def _start_collaboration(self):
        server_url=os.getenv("COLLAB_SERVER_URL","").strip(); key=self._collaboration_key()
        if not server_url or not key or not self.principal or not self.session_token:
            self.collaboration_status.setText("Collaboration: local")
            return
        if self.collaboration and self.collaboration.workbook_id==key:return
        self._stop_collaboration()
        client=RealtimeCollaborationClient(server_url,self.session_token,self.collaboration_bridge.event_received.emit)
        presence=PresencePayload(self.workbook.get_active_sheet().name,None)
        try:client.start(key,CollaborationIdentity(self.principal.user_id,self.principal.email),presence)
        except (OSError,RuntimeError) as exc:
            client.stop(); self.collaboration_status.setText("Collaboration: offline")
            self.statusBar().showMessage(f"Collaboration unavailable; continuing locally: {exc}",5000); return
        self.collaboration=client; self.collaboration_status.setText("Collaboration: connecting")

    def _stop_collaboration(self):
        client=self.collaboration; self.collaboration=None; self.collaboration_lock=None
        self.collaboration_participants={}
        if client:client.stop()
        if hasattr(self,"collaboration_status"):self.collaboration_status.setText("Collaboration: local")

    def _publish_presence(self,address):
        if not self.collaboration:return
        sheet=self.workbook.get_active_sheet().name
        if self.collaboration_lock:
            old_sheet,old_range=self.collaboration_lock
            if (old_sheet,old_range)!=(sheet,address):self.collaboration.release_advisory_lock(old_sheet,old_range); self.collaboration_lock=None
        try:
            self.collaboration.update_presence(PresencePayload(sheet,address))
            if address and self._can_edit() and self.collaboration.acquire_advisory_lock(sheet,address):self.collaboration_lock=(sheet,address)
        except (OSError,RuntimeError):pass

    def _collaboration_event(self,event):
        event_type=event.get("event") if isinstance(event,dict) else None
        if event_type=="connected":
            state=event.get("state",{}); self.collaboration_participants={p["session_id"]:p for p in state.get("participants",[])}
            for change in state.get("recent_changes",[]):self._apply_remote_change(change)
        elif event_type in {"presence.joined","presence.updated"}:
            presence=event.get("presence",{}); self.collaboration_participants[presence.get("session_id","")]=presence
            if self.collaboration and presence.get("session_id")!=self.collaboration.session_id:
                focus=presence.get("active_range") or presence.get("current_sheet") or "workbook"
                self.statusBar().showMessage(f"{presence.get('display_name','Another user')} is viewing {focus}",1800)
        elif event_type=="presence.left":
            self.collaboration_participants.pop(event.get("presence",{}).get("session_id"),None)
        elif event_type=="cell.updated":self._apply_remote_change(event.get("change",{}))
        elif event_type=="sync.required":
            for change in event.get("changes",[]):self._apply_remote_change(change)
        elif event_type=="lock.acquired":
            lock=event.get("lock",{})
            if self.collaboration and lock.get("holder_session_id")!=self.collaboration.session_id:
                self.statusBar().showMessage(f"{lock.get('holder_display_name','Another user')} is editing {lock.get('sheet_name')}!{lock.get('range_ref')}",2200)
        elif event_type=="access.revoked":
            self.collaboration_status.setText("Collaboration: access revoked")
            self.statusBar().showMessage("Your collaboration access was revoked. The local workbook remains open.",6000)
            return
        elif event_type in {"connection.error","connection.closed"}:
            self.collaboration_status.setText("Collaboration: reconnecting"); return
        if self.collaboration:self.collaboration_status.setText(f"Collaboration: connected · {len(self.collaboration_participants)} user(s)")

    def _apply_remote_change(self,change):
        if not self.collaboration or change.get("session_id")==self.collaboration.session_id:return
        sheet=next((item for item in self.workbook.sheets if item.name==change.get("sheet_name")),None)
        if sheet is None:return
        address=str(change.get("address") or "")
        try:CellAddress.parse(address)
        except ValueError:return
        cell=sheet.get_cell(address); cell.formula=change.get("formula"); cell.value=change.get("value")
        self.calculation.recalculate({self.calculation.cell_key(sheet.name,address)})
        for index in range(self.tabs.count()):
            view=self.tabs.widget(index)
            if isinstance(view,QTableView):view.model().refresh()
        self._mark_dirty(); self.statusBar().showMessage(f"Live update: {sheet.name}!{address}",1800)

    def closeEvent(self,event):
        if hasattr(self,"ai_dock") and self.ai_dock.worker is not None:
            QMessageBox.information(
                self,"AI request running","Wait for the current AI request to finish before closing."
            ); event.ignore(); return
        if self.dirty:
            answer=QMessageBox.question(
                self,"Unsaved changes","Save changes before closing?",
                QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel,
            )
            if answer==QMessageBox.StandardButton.Cancel:event.ignore(); return
            if answer==QMessageBox.StandardButton.Save and not self._save():event.ignore(); return
            if answer==QMessageBox.StandardButton.Discard and self.last_recovery_path:
                self.recovery.discard(self.last_recovery_path); self.last_recovery_path=None
        self._stop_collaboration(); super().closeEvent(event)
