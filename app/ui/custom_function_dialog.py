"""Context Studio-styled editor for local Python formula functions."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)

from app.engine.formula_engine import FormulaEngine
from app.services.custom_functions import CustomFunctionError, CustomFunctionService


_STARTER_SOURCE = '''def DOUBLE(value):
    """Return a number multiplied by two."""
    return float(value) * 2
'''


class CustomFunctionDialog(QDialog):
    """Create a validated function module and register it without restarting."""

    def __init__(
        self, engine: FormulaEngine, service: CustomFunctionService | None = None, parent=None
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.service = service or CustomFunctionService()
        self.saved_functions: tuple[str, ...] = ()
        self.setWindowTitle("Custom Python Functions")
        self.resize(720, 560)

        layout = QVBoxLayout(self)
        heading = QLabel("Create a spreadsheet function")
        heading.setObjectName("dialogHeading")
        layout.addWidget(heading)
        warning = QLabel(
            "Functions run locally on your computer. The editor blocks file, network, process and "
            "dynamic-code access. Only add code you understand. Use uppercase function names in formulas."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)
        form = QFormLayout()
        self.module_name = QLineEdit("my_functions")
        self.module_name.setPlaceholderText("Module filename")
        form.addRow("Module", self.module_name)
        layout.addLayout(form)
        self.editor = QPlainTextEdit(_STARTER_SOURCE)
        self.editor.setFont(QFont("Monospace"))
        self.editor.setTabStopDistance(32)
        layout.addWidget(self.editor)
        help_text = QLabel(
            "Available helpers: abs, min, max, sum, round, sorted, range, math and statistics. "
            "Example formula after saving: =DOUBLE(A1)"
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        validate_button = QPushButton("Validate")
        validate_button.clicked.connect(self._validate)
        layout.addWidget(validate_button)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self) -> None:
        try:
            names = self.service.validate(self.editor.toPlainText())
        except CustomFunctionError as exc:
            QMessageBox.warning(self, "Validation failed", str(exc))
            return
        QMessageBox.information(self, "Valid function module", f"Functions: {', '.join(names)}")

    def _save(self) -> None:
        try:
            result = self.service.save_and_register(
                self.module_name.text(), self.editor.toPlainText(), self.engine
            )
        except (CustomFunctionError, OSError) as exc:
            QMessageBox.warning(self, "Function not saved", str(exc))
            return
        self.saved_functions = result.function_names
        self.accept()
