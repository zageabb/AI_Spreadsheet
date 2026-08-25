from app.core.coordinates import CellAddress, CellRange, column_index_to_label, column_label_to_index


def test_columns_extend_beyond_z():
    assert column_index_to_label(25) == "Z"
    assert column_index_to_label(26) == "AA"
    assert column_index_to_label(16383) == "XFD"
    assert column_label_to_index("AA") == 26


def test_absolute_and_quoted_sheet_address_round_trip():
    address = CellAddress.parse("'Sales Data'!$AA$12")
    assert (address.row, address.column, address.sheet) == (11, 26, "Sales Data")
    assert address.a1() == "'Sales Data'!$AA$12"


def test_range_enumeration():
    assert [item.a1(False) for item in CellRange.parse("A1:B2").addresses()] == ["A1", "B1", "A2", "B2"]
