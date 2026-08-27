"""Dialogs for named ranges, conditional formats and basic Excel charts."""

from __future__ import annotations

import re

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPushButton, QVBoxLayout,
)


class NamedRangesDialog(QDialog):
    def __init__(self, names: list[dict], default_reference: str, sheet_names: list[str], parent=None):
        super().__init__(parent); self.setWindowTitle("Named ranges"); self.names=[dict(item) for item in names]
        layout=QVBoxLayout(self); self.list=QListWidget(); layout.addWidget(self.list)
        form=QFormLayout(); self.name=QLineEdit(); self.reference=QLineEdit(default_reference)
        self.scope=QComboBox(); self.scope.addItem("Workbook",None)
        for sheet in sheet_names:self.scope.addItem(sheet,sheet)
        form.addRow("Name",self.name); form.addRow("Refers to",self.reference); form.addRow("Scope",self.scope); layout.addLayout(form)
        row=QHBoxLayout(); add=QPushButton("Add"); remove=QPushButton("Remove selected"); row.addWidget(add); row.addWidget(remove); layout.addLayout(row)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); layout.addWidget(buttons)
        add.clicked.connect(self._add); remove.clicked.connect(self._remove); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        self._refresh()

    def _refresh(self):
        self.list.clear()
        for item in self.names:self.list.addItem(f"{item['name']} → {item['refers_to']} ({item.get('scope') or 'Workbook'})")

    def _add(self):
        name=self.name.text().strip(); reference=self.reference.text().strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*",name) or re.fullmatch(r"[A-Za-z]{1,3}[1-9][0-9]*",name):
            QMessageBox.warning(self,"Invalid name","Use a name beginning with a letter or underscore; cell addresses are not allowed."); return
        if not reference:
            QMessageBox.warning(self,"Invalid reference","Enter a cell or range reference."); return
        scope=self.scope.currentData(); self.names=[item for item in self.names if not (item.get("name","").casefold()==name.casefold() and item.get("scope")==scope)]
        self.names.append({"name":name,"refers_to":reference if reference.startswith("=") else "="+reference,"scope":scope}); self._refresh()

    def _remove(self):
        row=self.list.currentRow()
        if row>=0:self.names.pop(row); self._refresh()


class ConditionalFormatDialog(QDialog):
    def __init__(self, range_ref: str, parent=None):
        super().__init__(parent); self.setWindowTitle("Conditional formatting")
        form=QFormLayout(self); self.range=QLineEdit(range_ref); self.operator=QComboBox()
        for label,value in (("Greater than","greaterThan"),("Greater than or equal","greaterThanOrEqual"),("Less than","lessThan"),("Less than or equal","lessThanOrEqual"),("Equal to","equal"),("Not equal to","notEqual"),("Between","between")):self.operator.addItem(label,value)
        self.value1=QLineEdit(); self.value2=QLineEdit(); self.fill=QLineEdit("FFF2CC"); self.font=QLineEdit("9C6500")
        form.addRow("Apply to",self.range); form.addRow("Rule",self.operator); form.addRow("Value",self.value1); form.addRow("Second value",self.value2); form.addRow("Fill colour",self.fill); form.addRow("Font colour",self.font)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); form.addRow(buttons); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)

    def rule(self):
        values=[self._formula(self.value1.text())]
        if self.operator.currentData() in {"between","notBetween"}:values.append(self._formula(self.value2.text()))
        return {"range":self.range.text().strip(),"type":"cellIs","operator":self.operator.currentData(),"formula":values,"fill_color":self.fill.text().strip().lstrip("#"),"font_color":self.font.text().strip().lstrip("#")}

    @staticmethod
    def _formula(value):
        text=value.strip()
        try:float(text); return text
        except ValueError:return f'"{text}"'


class ChartDialog(QDialog):
    def __init__(self, range_ref: str, default_anchor: str, parent=None):
        super().__init__(parent); self.setWindowTitle("Create chart")
        form=QFormLayout(self); self.chart_type=QComboBox(); self.chart_type.addItems(["Column","Line","Pie"])
        self.title=QLineEdit("Chart"); self.range=QLineEdit(range_ref); self.anchor=QLineEdit(default_anchor)
        form.addRow("Chart type",self.chart_type); form.addRow("Title",self.title); form.addRow("Data range",self.range); form.addRow("Place at",self.anchor)
        form.addRow(QLabel("The first row supplies series names; the first column supplies categories."))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); form.addRow(buttons); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)

    def chart(self):
        return {"type":self.chart_type.currentText().lower(),"title":self.title.text().strip() or "Chart","range":self.range.text().strip(),"anchor":self.anchor.text().strip() or "E2"}
