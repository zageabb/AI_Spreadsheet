from app.models.sheet import Worksheet
from app.services.worksheet_editing import (
    CellRange, apply_format, clear_cells, delete_columns, delete_rows,
    insert_columns, insert_rows, replace_text, restore, snapshot, sort_rows,
)


def test_snapshot_restore_and_formatting_are_reversible():
    sheet = Worksheet("Data")
    sheet.get_cell("A1").value = "Original"
    before = snapshot(sheet)
    apply_format(sheet, CellRange(0, 0, 0, 1), {"bold": True, "number_format": "0.00"})
    clear_cells(sheet, CellRange(0, 0, 0, 0))
    assert "A1" not in sheet.cells
    assert sheet.cells["B1"].formatting["bold"] is True
    restore(sheet, before)
    assert sheet.cells["A1"].value == "Original"
    assert "B1" not in sheet.cells


def test_insert_and_delete_rows_and_columns_shift_sparse_cells():
    sheet = Worksheet("Data")
    sheet.get_cell("B2").value = "move"
    insert_rows(sheet, 1, 2)
    assert sheet.cells["B4"].value == "move"
    delete_rows(sheet, 1, 1)
    assert sheet.cells["B3"].value == "move"
    insert_columns(sheet, 1, 2)
    assert sheet.cells["D3"].value == "move"
    delete_columns(sheet, 2, 1)
    assert sheet.cells["C3"].value == "move"


def test_structural_edits_adjust_local_formula_references():
    sheet = Worksheet("Data")
    sheet.get_cell("A1").formula = "=B2+$C$3+'Other'!D4"
    insert_rows(sheet, 1)
    assert sheet.cells["A1"].formula == "=B3+$C$4+'Other'!D4"
    delete_columns(sheet, 1)
    assert sheet.cells["A1"].formula == "=#REF!+$B$4+'Other'!D4"


def test_deleting_selected_rows_and_columns_removes_their_cells():
    sheet = Worksheet("Data")
    sheet.get_cell("A1").value = "remove row"
    sheet.get_cell("B2").value = "remove column"
    delete_rows(sheet, 0)
    assert "A1" not in sheet.cells
    assert sheet.cells["B1"].value == "remove column"
    delete_columns(sheet, 1)
    assert not sheet.cells


def test_replace_text_supports_case_and_formula_content():
    sheet = Worksheet("Data")
    sheet.get_cell("A1").value = "North NORTH"
    sheet.get_cell("A2").formula = '=IF(B2="North",1,0)'
    assert replace_text(sheet, "north", "South") == 2
    assert sheet.cells["A1"].value == "South South"
    assert "South" in sheet.cells["A2"].formula
    assert replace_text(sheet, "south", "x", match_case=True) == 0


def test_sort_rows_keeps_row_payloads_together():
    sheet = Worksheet("Data")
    for row, (name, score) in enumerate((("Beta", 2), ("Alpha", 3), ("Gamma", 1))):
        sheet.get_cell(f"A{row + 1}").value = name
        sheet.get_cell(f"B{row + 1}").value = score
    sort_rows(sheet, CellRange(0, 0, 2, 1), 1)
    assert [(sheet.cells[f"A{row}"].value, sheet.cells[f"B{row}"].value) for row in range(1, 4)] == [
        ("Gamma", 1), ("Beta", 2), ("Alpha", 3)
    ]
