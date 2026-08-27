"""Modeless Context Studio-styled find and replace panel."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QGridLayout, QLabel, QLineEdit, QPushButton,
)


class FindReplaceDialog(QDialog):
    find_next = Signal(str, bool)
    replace_one = Signal(str, str, bool)
    replace_all = Signal(str, str, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Find and replace")
        self.setModal(False)
        layout = QGridLayout(self)
        self.find_edit = QLineEdit(); self.replace_edit = QLineEdit()
        self.case_box = QCheckBox("Match case")
        layout.addWidget(QLabel("Find"), 0, 0); layout.addWidget(self.find_edit, 0, 1, 1, 3)
        layout.addWidget(QLabel("Replace"), 1, 0); layout.addWidget(self.replace_edit, 1, 1, 1, 3)
        layout.addWidget(self.case_box, 2, 1)
        find_button = QPushButton("Find next")
        replace_button = QPushButton("Replace")
        all_button = QPushButton("Replace all")
        layout.addWidget(find_button, 3, 1); layout.addWidget(replace_button, 3, 2); layout.addWidget(all_button, 3, 3)
        find_button.clicked.connect(self._find)
        replace_button.clicked.connect(self._replace)
        all_button.clicked.connect(self._replace_all)
        self.find_edit.returnPressed.connect(self._find)

    def focus_find(self) -> None:
        self.find_edit.setFocus(); self.find_edit.selectAll()

    def _find(self) -> None:
        self.find_next.emit(self.find_edit.text(), self.case_box.isChecked())

    def _replace(self) -> None:
        self.replace_one.emit(self.find_edit.text(), self.replace_edit.text(), self.case_box.isChecked())

    def _replace_all(self) -> None:
        self.replace_all.emit(self.find_edit.text(), self.replace_edit.text(), self.case_box.isChecked())
