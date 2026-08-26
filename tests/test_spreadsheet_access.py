import pytest

pytest.importorskip(
    "PySide6.QtGui", reason="Qt GUI libraries are unavailable", exc_type=ImportError
)

from PySide6.QtCore import QCoreApplication, Qt

from app.models.sheet import Worksheet
from app.ui.spreadsheet_model import SpreadsheetTableModel


def test_viewer_model_rejects_cell_edits():
    application = QCoreApplication.instance() or QCoreApplication([])
    del application
    sheet = Worksheet("Read only")
    model = SpreadsheetTableModel(sheet, rows=10, columns=10, editable=False)
    index = model.index(0, 0)

    assert not model.flags(index) & Qt.ItemFlag.ItemIsEditable
    assert model.setData(index, "blocked") is False
    assert "A1" not in sheet.cells
