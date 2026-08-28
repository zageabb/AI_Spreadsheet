"""Context Studio-styled manager for secret-free analytical connection profiles."""

from __future__ import annotations

from copy import deepcopy
import json

from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from app.services.data_connectors import DataConnectorError, DataConnectorService, DataSourceSpec


class DataConnectionDialog(QDialog):
    """Create, preview and select workbook-safe REST/PostgreSQL profiles."""

    def __init__(self, profiles: list[dict], service: DataConnectorService, parent=None) -> None:
        super().__init__(parent); self.setWindowTitle("Data connections"); self.resize(980,650)
        self.profiles=deepcopy([item for item in profiles if isinstance(item,dict)]); self.service=service
        self.selected_spec: DataSourceSpec | None=None
        root=QVBoxLayout(self); note=QLabel("Credentials stay outside the workbook. Enter only a credential reference configured in the environment."); note.setWordWrap(True); root.addWidget(note)
        splitter=QSplitter(); root.addWidget(splitter,1)
        left=QWidget(); left_layout=QVBoxLayout(left); self.list=QListWidget(); left_layout.addWidget(self.list)
        new_profile=QPushButton("New profile"); remove=QPushButton("Remove profile"); left_layout.addWidget(new_profile); left_layout.addWidget(remove); splitter.addWidget(left)
        right=QWidget(); right_layout=QVBoxLayout(right); form=QFormLayout()
        self.profile_name=QLineEdit(); self.kind=QComboBox(); self.kind.addItem("REST API","rest"); self.kind.addItem("PostgreSQL analytics","postgres_analytics")
        self.location=QLineEdit(); self.location.setPlaceholderText("https://api.example.com/data or a PostgreSQL connection label")
        self.credential=QLineEdit(); self.credential.setPlaceholderText("e.g. finance_api or reporting_db")
        self.query=QPlainTextEdit(); self.query.setPlaceholderText("Read-only SELECT or WITH query for PostgreSQL")
        self.params=QPlainTextEdit("{}"); self.params.setMaximumHeight(70); self.headers=QPlainTextEdit("{}"); self.headers.setMaximumHeight(70)
        self.json_path=QLineEdit(); self.json_path.setPlaceholderText("Optional, e.g. data.records")
        self.limit=QSpinBox(); self.limit.setRange(1,1_000_000); self.limit.setValue(100_000)
        for label,widget in (("Profile name",self.profile_name),("Type",self.kind),("Location",self.location),("Credential reference",self.credential),("PostgreSQL query",self.query),("REST parameters (JSON)",self.params),("REST headers (JSON, non-secret)",self.headers),("REST JSON path",self.json_path),("Row limit",self.limit)):form.addRow(label,widget)
        right_layout.addLayout(form)
        actions=QHBoxLayout(); save=QPushButton("Save profile"); preview=QPushButton("Preview 50 rows"); load=QPushButton("Load into sheet"); close=QPushButton("Close")
        for button in (save,preview,load,close):actions.addWidget(button)
        right_layout.addLayout(actions); self.preview_table=QTableWidget(); right_layout.addWidget(self.preview_table,1); splitter.addWidget(right); splitter.setStretchFactor(1,1)
        self.list.currentRowChanged.connect(self._profile_selected); self.kind.currentIndexChanged.connect(self._sync_fields)
        new_profile.clicked.connect(lambda:(self.list.clearSelection(),self.list.setCurrentRow(-1),self._clear_form()))
        save.clicked.connect(self._save_profile); remove.clicked.connect(self._remove_profile); preview.clicked.connect(self._preview); load.clicked.connect(self._load); close.clicked.connect(self.accept)
        self._refresh_list(); self._sync_fields()

    def _sync_fields(self):
        postgres=self.kind.currentData()=="postgres_analytics"
        self.query.setEnabled(postgres); self.params.setEnabled(not postgres); self.headers.setEnabled(not postgres); self.json_path.setEnabled(not postgres)

    def _source(self) -> DataSourceSpec:
        kind=str(self.kind.currentData()); credential=self.credential.text().strip(); limit=self.limit.value()
        if kind=="rest":
            options={"credential_ref":credential,"params":self._json_object(self.params.toPlainText(),"parameters"),"headers":self._json_object(self.headers.toPlainText(),"headers"),"json_path":self.json_path.text().strip(),"limit":limit}
        else:options={"credential_ref":credential,"query":self.query.toPlainText().strip(),"limit":limit}
        source=DataSourceSpec(kind,self.location.text().strip(),options); source.to_dict(); return source

    @staticmethod
    def _json_object(text,label):
        try:value=json.loads(text or "{}")
        except json.JSONDecodeError as exc:raise DataConnectorError(f"REST {label} must be valid JSON") from exc
        if not isinstance(value,dict):raise DataConnectorError(f"REST {label} must be a JSON object")
        return value

    def _save_profile(self):
        name=self.profile_name.text().strip()
        if not name:QMessageBox.warning(self,"Profile name","Enter a profile name."); return
        try:payload={"name":name,"source":self._source().to_dict()}
        except DataConnectorError as exc:QMessageBox.warning(self,"Invalid connection",str(exc)); return
        current=self.list.currentRow()
        if current>=0:self.profiles[current]=payload
        else:self.profiles.append(payload)
        self._refresh_list(); self.list.setCurrentRow(current if current>=0 else len(self.profiles)-1)

    def _remove_profile(self):
        row=self.list.currentRow()
        if row>=0:self.profiles.pop(row); self._refresh_list(); self._clear_form()

    def _preview(self):
        try:source=self._source(); QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); rows=self.service.preview(source,50)
        except DataConnectorError as exc:QMessageBox.warning(self,"Connection preview failed",str(exc)); return
        finally:QApplication.restoreOverrideCursor()
        columns=list(dict.fromkeys(str(key) for row in rows for key in row))
        self.preview_table.setRowCount(len(rows)); self.preview_table.setColumnCount(len(columns)); self.preview_table.setHorizontalHeaderLabels(columns)
        for row_index,row in enumerate(rows):
            for column_index,column in enumerate(columns):self.preview_table.setItem(row_index,column_index,QTableWidgetItem("" if row.get(column) is None else str(row.get(column))))
        self.preview_table.resizeColumnsToContents()

    def _load(self):
        try:self.selected_spec=self._source()
        except DataConnectorError as exc:QMessageBox.warning(self,"Invalid connection",str(exc)); return
        self.accept()

    def _refresh_list(self):
        self.list.clear()
        for item in self.profiles:self.list.addItem(str(item.get("name") or "Unnamed connection"))

    def _profile_selected(self,row):
        if row<0 or row>=len(self.profiles):return
        item=self.profiles[row]; payload=item.get("source",{})
        try:source=DataSourceSpec.from_dict(payload)
        except (KeyError,TypeError,ValueError):return
        self.profile_name.setText(str(item.get("name") or "")); index=self.kind.findData(source.kind)
        if index>=0:self.kind.setCurrentIndex(index)
        self.location.setText(source.location); options=source.options; self.credential.setText(str(options.get("credential_ref") or "")); self.query.setPlainText(str(options.get("query") or "")); self.params.setPlainText(json.dumps(options.get("params",{}),indent=2)); self.headers.setPlainText(json.dumps(options.get("headers",{}),indent=2)); self.json_path.setText(str(options.get("json_path") or "")); self.limit.setValue(int(options.get("limit",100_000))); self._sync_fields()

    def _clear_form(self):
        self.profile_name.clear(); self.location.clear(); self.credential.clear(); self.query.clear(); self.params.setPlainText("{}"); self.headers.setPlainText("{}"); self.json_path.clear()
