"""Context Studio-styled desktop shell with a virtual spreadsheet grid."""
from __future__ import annotations

import os
from pathlib import Path
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QStatusBar,
    QTabWidget, QTableView, QToolBar, QVBoxLayout, QWidget)

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
from app.storage import get_workbook_storage
from app.storage.postgres_storage import PostgresStorageError, PostgresWorkbookStorage
from app.ui.spreadsheet_model import SpreadsheetTableModel
from app.ui.theme import CONTEXT_STUDIO_QSS
from app.ui.transformation_dialog import TransformationDialog
from app.ui.sharing_dialog import SharingDialog


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
        self.engine = FormulaEngine(); register_builtin_functions(self.engine); PluginLoader().load(self.engine)
        self.workbook = self._owned_workbook("Untitled"); self.workbook.add_sheet("Sheet1")
        self.calculation = WorkbookCalculationService(self.workbook, self.engine)
        self.current_file_path: str | None = None; self.dirty = False; self.access_role = "owner"
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
        self.transform_a=self._make_action("Transform Data","Ctrl+Shift+T",self._transform_data)
        self.connect_csv_a=self._make_action("Connect CSV",None,self._connect_csv)
        self.connect_sqlite_a=self._make_action("Connect SQLite",None,self._connect_sqlite)
        self.refresh_data_a=self._make_action("Refresh Data","Ctrl+Alt+R",self._refresh_data)
        self.share_a=self._make_action("Share Workbook",None,self._share_workbook)
        self.sign_out_a=self._make_action("Sign Out",None,self.close)

    def _chrome(self):
        file_menu=self.menuBar().addMenu("File"); file_menu.addActions([self.new_a,self.open_a,self.save_a,self.saveas_a,self.xlsx_in,self.csv_in,self.xlsx_out,self.csv_out]); file_menu.addSeparator(); file_menu.addAction(self.sign_out_a)
        edit_menu=self.menuBar().addMenu("Edit"); edit_menu.addActions([self.copy_a,self.paste_a])
        sheet_menu=self.menuBar().addMenu("Sheet"); sheet_menu.addActions([self.add_a,self.rename_a,self.delete_a])
        data_menu=self.menuBar().addMenu("Data"); data_menu.addActions([self.connect_csv_a,self.connect_sqlite_a,self.refresh_data_a]); data_menu.addSeparator(); data_menu.addAction(self.transform_a)
        access_menu=self.menuBar().addMenu("Access"); access_menu.addAction(self.share_a)
        bar=QToolBar("Workbook"); bar.setMovable(False); bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        bar.addActions([self.new_a,self.open_a,self.save_a]); bar.addSeparator(); bar.addActions([self.copy_a,self.paste_a]); bar.addSeparator(); bar.addAction(self.add_a); self.addToolBar(bar)
        root=QWidget(); layout=QVBoxLayout(root); layout.setContentsMargins(10,10,10,8)
        formula=QHBoxLayout(); self.name_box=QLineEdit("A1"); self.name_box.setFixedWidth(90); self.name_box.returnPressed.connect(self._go)
        self.formula_bar=QLineEdit(); self.formula_bar.setPlaceholderText("Enter a value or formula"); self.formula_bar.returnPressed.connect(self._apply_formula)
        formula.addWidget(self.name_box); formula.addWidget(QLabel("fx")); formula.addWidget(self.formula_bar); layout.addLayout(formula)
        self.tabs=QTabWidget(); self.tabs.setDocumentMode(True); self.tabs.setMovable(True); self.tabs.currentChanged.connect(self._tab_changed)
        plus=QPushButton("+"); plus.clicked.connect(self._add_sheet); self.tabs.setCornerWidget(plus); layout.addWidget(self.tabs); self.setCentralWidget(root)
        status=QStatusBar(); self.cell_status=QLabel("Cell: A1"); self.selection_status=QLabel("Selection: 1"); self.collaboration_status=QLabel("Collaboration: local"); self.identity_status=QLabel(self._identity_label()); status.addPermanentWidget(self.collaboration_status); status.addPermanentWidget(self.identity_status); status.addPermanentWidget(self.cell_status); status.addPermanentWidget(self.selection_status); self.setStatusBar(status)

    def _view(self, index):
        view=QTableView(); model=SpreadsheetTableModel(self.workbook.sheets[index], evaluator=self._evaluate, editable=self._can_edit()); view.setModel(model)
        view.setAlternatingRowColors(True); view.setSelectionMode(QTableView.SelectionMode.ContiguousSelection); view.horizontalHeader().setDefaultSectionSize(105); view.verticalHeader().setDefaultSectionSize(23)
        view.selectionModel().currentChanged.connect(self._selected); view.selectionModel().selectionChanged.connect(self._selection); model.cell_edited.connect(self._edited); return view

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

    def _edited(self,address,*_):
        sheet=self.workbook.get_active_sheet()
        self.calculation.recalculate({self.calculation.cell_key(sheet.name,address)})
        for index in range(self.tabs.count()):
            view=self.tabs.widget(index)
            if isinstance(view,QTableView): view.model().refresh()
        self._mark_dirty()
        if self.collaboration:
            cell=sheet.cells.get(address)
            try:self.collaboration.publish_cell_change(sheet.name,address,cell.value if cell else None,cell.formula if cell else None)
            except CollaborationConflict as exc:self.statusBar().showMessage(f"Collaboration conflict: {exc}. Your local edit was not broadcast.",6000)
            except (OSError,RuntimeError) as exc:self.statusBar().showMessage(f"Collaboration offline: {exc}",4000)
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

    def _new(self):
        self._stop_collaboration(); self.workbook=self._owned_workbook("Untitled"); self.workbook.add_sheet("Sheet1"); self.access_role="owner"; self.calculation=WorkbookCalculationService(self.workbook,self.engine); self.current_file_path=None; self.dirty=False; self._tabs(); self._title()

    def _open(self):
        if isinstance(self.storage,PostgresWorkbookStorage):
            path,ok=QInputDialog.getText(self,"Open PostgreSQL workbook","Workbook key:")
            if not ok:path=""
        else:path,_=QFileDialog.getOpenFileName(self,"Open workbook","","AI Workbook (*.json)")
        if not path:return
        try:
            if isinstance(self.storage,PostgresWorkbookStorage) and self.principal:
                workbook=self.storage.load_workbook_for_user(path,self.principal.email)
            else:workbook=self.storage.load_workbook(path)
        except (OSError,PostgresStorageError) as exc: QMessageBox.warning(self,"Open failed",str(exc)); return
        role,claimed=self.permission_service.resolve_or_claim(self.principal.email,workbook) if self.principal else ("owner",False)
        if role is None:QMessageBox.warning(self,"Access denied","You do not have access to this workbook."); return
        self.workbook=workbook; self.access_role=role
        self.calculation=WorkbookCalculationService(self.workbook,self.engine); self.calculation.recalculate(); self.current_file_path=path; self.dirty=claimed; self._tabs(); self._title()
        if claimed:self.statusBar().showMessage("This legacy workbook is now assigned to you; save it to persist ownership.",5000)
        self._start_collaboration()

    def _save(self):
        if not self._can_edit():QMessageBox.warning(self,"Read only","Viewers cannot save changes to this workbook."); return
        if not self.current_file_path:self._save_as(); return
        try:
            if isinstance(self.storage,PostgresWorkbookStorage) and self.principal:
                self.storage.save_workbook_for_user(self.current_file_path,self.workbook,self.principal.email)
            else:self.storage.save_workbook(self.current_file_path,self.workbook)
        except (OSError,PostgresStorageError) as exc:QMessageBox.warning(self,"Save failed",str(exc)); return
        self.dirty=False; self._title()
        self._start_collaboration()

    def _save_as(self):
        if not self._can_edit():return
        if isinstance(self.storage,PostgresWorkbookStorage):
            path,ok=QInputDialog.getText(self,"Save PostgreSQL workbook","Workbook key:",text=self.current_file_path or "")
            if not ok:path=""
            if path:self.current_file_path=path.strip(); self._save()
        else:
            path,_=QFileDialog.getSaveFileName(self,"Save workbook","","AI Workbook (*.json)")
            if path:self.current_file_path=path if path.endswith(".json") else path+".json"; self._save()

    def _import(self,kind):
        pattern="Excel Workbook (*.xlsx)" if kind=="xlsx" else "CSV File (*.csv)"; path,_=QFileDialog.getOpenFileName(self,"Import","",pattern)
        if not path:return
        try:self.workbook=(self.converter.import_xlsx(path) if kind=="xlsx" else self.converter.import_csv(path))
        except WorkbookConversionError as exc: QMessageBox.warning(self,"Import failed",str(exc)); return
        if self.principal:self.workbook.permissions=self.permission_service.assign_owner(self.workbook.permissions,self.principal.email)
        self.access_role="owner"; self.calculation=WorkbookCalculationService(self.workbook,self.engine); self.calculation.recalculate(); self.current_file_path=None; self.dirty=True; self._tabs(); self._title()

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
        for action in [self.save_a,self.saveas_a,self.add_a,self.rename_a,self.delete_a,self.paste_a,self.transform_a,self.connect_csv_a,self.connect_sqlite_a,self.refresh_data_a]:action.setEnabled(editable)
        self.share_a.setEnabled(self.access_role=="owner")
        self.formula_bar.setReadOnly(not editable)
        corner=self.tabs.cornerWidget()
        if corner:corner.setEnabled(editable)
        if hasattr(self,"identity_status"):self.identity_status.setText(self._identity_label())

    def _share_workbook(self):
        if not self.principal or self.access_role!="owner":return
        dialog=SharingDialog(self.workbook,self.principal.email,self.permission_service,self)
        dialog.exec()
        if dialog.changed:
            self.access_role=self._resolve_access(self.workbook) or "viewer"
            self._mark_dirty(); self._tabs()

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
        self._stop_collaboration(); super().closeEvent(event)
