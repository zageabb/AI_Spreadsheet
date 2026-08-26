"""Preview and apply recorded worksheet transformations."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QLabel, QListWidget, QMessageBox, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from app.services.transformations import TransformationPipeline, TransformationStep


class TransformationDialog(QDialog):
    """Small Power Query-style step builder with before-apply preview."""

    def __init__(self, rows: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Transform Data")
        self.resize(980, 650)
        self.source_rows = rows
        self.steps: list[TransformationStep] = []
        self.result_rows = [dict(row) for row in rows]
        self._build_ui()
        self._refresh_preview()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        heading = QLabel("Transformation steps")
        heading.setStyleSheet("font-size:18px;font-weight:700;color:#15233a")
        layout.addWidget(heading)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        controls = QWidget(); control_layout = QVBoxLayout(controls)
        form = QFormLayout()
        self.operation = QComboBox(); self.operation.addItems(["Filter", "Sort", "Fill null"])
        self.column = QComboBox(); self.column.addItems(list(self.source_rows[0]) if self.source_rows else [])
        self.operator = QComboBox(); self.operator.addItems(["equals", "not equal", "contains", "greater than", "less than"])
        self.value = QComboBox(); self.value.setEditable(True)
        form.addRow("Operation", self.operation); form.addRow("Column", self.column)
        form.addRow("Condition", self.operator); form.addRow("Value", self.value)
        control_layout.addLayout(form)
        add = QPushButton("Add step"); add.clicked.connect(self._add_step); control_layout.addWidget(add)
        self.step_list = QListWidget(); control_layout.addWidget(self.step_list)
        remove = QPushButton("Remove selected step"); remove.clicked.connect(self._remove_step); control_layout.addWidget(remove)
        splitter.addWidget(controls)
        self.preview = QTableWidget(); self.preview.setAlternatingRowColors(True); splitter.addWidget(self.preview)
        splitter.setSizes([300, 680]); layout.addWidget(splitter)
        self.summary = QLabel(); layout.addWidget(self.summary)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Apply).setText("Apply to sheet")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def _add_step(self) -> None:
        if not self.column.currentText():
            return
        operation = self.operation.currentText()
        column, raw_value = self.column.currentText(), self.value.currentText()
        if operation == "Filter":
            operator_names = {"equals": "eq", "not equal": "ne", "contains": "contains",
                              "greater than": "gt", "less than": "lt"}
            step = TransformationStep("filter", {"column": column,
                "operator": operator_names[self.operator.currentText()], "value": self._scalar(raw_value)})
        elif operation == "Sort":
            step = TransformationStep("sort", {"column": column,
                "descending": raw_value.strip().lower() in {"descending", "desc", "true", "yes"}})
        else:
            step = TransformationStep("fill_null", {"column": column, "value": self._scalar(raw_value)})
        candidate = [*self.steps, step]
        try:
            TransformationPipeline(candidate).apply(self.source_rows)
        except (TypeError, ValueError) as exc:
            QMessageBox.warning(self, "Invalid step", str(exc)); return
        self.steps = candidate
        self.step_list.addItem(self._describe(step))
        self._refresh_preview()

    def _remove_step(self) -> None:
        row = self.step_list.currentRow()
        if row < 0:
            return
        del self.steps[row]; self.step_list.takeItem(row); self._refresh_preview()

    def _refresh_preview(self) -> None:
        self.result_rows = TransformationPipeline(self.steps).apply(self.source_rows)
        headers = list(self.result_rows[0]) if self.result_rows else (list(self.source_rows[0]) if self.source_rows else [])
        preview_rows = self.result_rows[:200]
        self.preview.setRowCount(len(preview_rows)); self.preview.setColumnCount(len(headers)); self.preview.setHorizontalHeaderLabels(headers)
        for row_index, row in enumerate(preview_rows):
            for column_index, header in enumerate(headers):
                value = row.get(header)
                self.preview.setItem(row_index, column_index, QTableWidgetItem("" if value is None else str(value)))
        self.preview.resizeColumnsToContents()
        self.summary.setText(f"{len(self.result_rows):,} rows after {len(self.steps)} step(s). Preview limited to 200 rows.")

    @staticmethod
    def _scalar(value: str):
        text = value.strip()
        if text.lower() in {"true", "false"}: return text.lower() == "true"
        if text == "": return None
        try: return int(text)
        except ValueError:
            try: return float(text)
            except ValueError: return value

    @staticmethod
    def _describe(step: TransformationStep) -> str:
        params = ", ".join(f"{key}={value}" for key, value in step.parameters.items())
        return f"{step.operation}: {params}"
