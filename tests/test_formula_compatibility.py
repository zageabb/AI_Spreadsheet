from datetime import date

import pytest

from app.engine.calculation_service import WorkbookCalculationService
from app.engine.formula_engine import FormulaEngine
from app.formulas.registry import register_builtin_functions
from app.models.workbook import Workbook


def _engine():
    engine = FormulaEngine(); register_builtin_functions(engine)
    return engine


def _workbook_service():
    workbook = Workbook(name="Functions")
    data = workbook.add_sheet("Data")
    summary = workbook.add_sheet("Summary")
    engine = _engine()
    return workbook, data, summary, WorkbookCalculationService(workbook, engine)


def test_lookup_functions_keep_range_shape():
    _workbook, data, summary, service = _workbook_service()
    rows = [("A", "Alpha", 10), ("B", "Beta", 20), ("C", "Gamma", 30)]
    for row_index, row in enumerate(rows, start=1):
        for column, value in zip(("A", "B", "C"), row):
            data.get_cell(f"{column}{row_index}").value = value
    summary.get_cell("A1").formula = '=VLOOKUP("B",Data!A1:C3,3,FALSE)'
    summary.get_cell("A2").formula = '=INDEX(Data!A1:C3,3,2)'
    summary.get_cell("A3").formula = '=XLOOKUP("A",Data!A1:A3,Data!B1:B3,"Missing")'
    service.recalculate()
    assert summary.get_cell("A1").value == 20
    assert summary.get_cell("A2").value == "Gamma"
    assert summary.get_cell("A3").value == "Alpha"


def test_conditional_aggregates():
    _workbook, data, summary, service = _workbook_service()
    for index, (category, value) in enumerate((("Hardware", 10), ("Software", 30), ("Hardware", 20)), start=1):
        data.get_cell(f"A{index}").value = category
        data.get_cell(f"B{index}").value = value
    summary.get_cell("A1").formula = '=COUNTIF(Data!A1:A3,"Hardware")'
    summary.get_cell("A2").formula = '=SUMIF(Data!A1:A3,"Hardware",Data!B1:B3)'
    summary.get_cell("A3").formula = '=AVERAGEIF(Data!A1:A3,"Hardware",Data!B1:B3)'
    service.recalculate()
    assert [summary.get_cell(f"A{i}").value for i in range(1, 4)] == [2.0, 30.0, 15.0]


def test_dates_text_and_math_functions():
    engine = _engine()
    assert engine.evaluate("=YEAR(DATE(2026,8,26))") == 2026.0
    assert engine.evaluate("=EOMONTH(DATE(2026,2,10),0)") == date(2026, 2, 28)
    assert engine.evaluate('=TEXTJOIN("-",TRUE,"A","",UPPER("b"))') == "A-B"
    assert engine.evaluate("=SUMPRODUCT(2,3)") == 6.0
    assert engine.evaluate("=SQRT(-1)") == "#NUM!"


def test_lookup_not_found_preserves_error_code():
    engine = _engine()
    assert engine.evaluate('=MATCH("missing","present",0)') == "#N/A"


def test_dynamic_arrays_spill_and_report_blocked_ranges():
    workbook, _data, summary, service = _workbook_service()
    summary.get_cell("A1").formula = "=SEQUENCE(2,3,1,1)"
    summary.get_cell("H1").formula = "=B2*10"
    service.recalculate()
    assert [[summary.get_cell(f"{column}{row}").value for column in "ABC"] for row in (1, 2)] == [
        [1.0, 2.0, 3.0], [4.0, 5.0, 6.0]
    ]
    assert summary.get_cell("H1").value == 50.0

    summary.get_cell("E2").value = "occupied"
    summary.get_cell("D1").formula = "=SEQUENCE(2,2)"
    service.recalculate()
    assert summary.get_cell("D1").value == "#SPILL!"
    assert summary.get_cell("E1").value is None


def test_filter_sort_unique_and_structured_table_references():
    _workbook, data, summary, service = _workbook_service()
    for row, values in enumerate((("Category", "Amount"), ("B", 20), ("A", 10), ("B", 20)), 1):
        for column, value in zip("AB", values):
            data.get_cell(f"{column}{row}").value = value
    data.metadata["tables"] = [{
        "name": "SalesTable", "display_name": "SalesTable", "ref": "A1:B4",
        "columns": ["Category", "Amount"], "totals_row_shown": False,
    }]
    summary.get_cell("A1").formula = "=SUM(SalesTable[Amount])"
    summary.get_cell("C1").formula = "=UNIQUE(SalesTable[Category])"
    summary.get_cell("E1").formula = "=SORT(SalesTable[Amount],1,-1)"
    summary.get_cell("G1").formula = '=FILTER(Data!A2:B4,Data!A2:A4="B","none")'
    service.recalculate()
    assert summary.get_cell("A1").value == 50.0
    assert [summary.get_cell(f"C{row}").value for row in range(1, 3)] == ["B", "A"]
    assert [summary.get_cell(f"E{row}").value for row in range(1, 4)] == [20, 20, 10]
    assert [[summary.get_cell(f"{column}{row}").value for column in "GH"] for row in (1, 2)] == [
        ["B", 20], ["B", 20]
    ]


def test_named_ranges_participate_in_calculation_and_dependencies():
    workbook,data,summary,service=_workbook_service()
    for row,value in enumerate((10,20,30),1):data.get_cell(f"B{row}").value=value
    workbook.metadata["defined_names"]=[{"name":"SalesValues","refers_to":"=Data!$B$1:$B$3","scope":None}]
    summary.get_cell("A1").formula="=SUM(SalesValues)"
    service.recalculate()
    assert summary.get_cell("A1").value==60.0
    data.get_cell("B2").value=25
    service.recalculate({service.cell_key("Data","B2")})
    assert summary.get_cell("A1").value==65.0


def test_phase_13_statistical_rounding_text_and_date_functions():
    engine=_engine()
    assert engine.evaluate("=MEDIAN(1,8,3)")==3.0
    assert engine.evaluate("=STDEV.S(2,4,4,4,5,5,7,9)")==pytest.approx(2.138089935)
    assert engine.evaluate("=LARGE(SEQUENCE(3),2)")==2.0
    assert engine.evaluate("=ROUNDUP(1.231,2)")==1.24
    assert engine.evaluate("=ROUNDDOWN(-1.239,2)")==-1.23
    assert engine.evaluate('=SEARCH("B","abc")')==2.0
    assert engine.evaluate('=REPLACE("abcdef",2,3,"X")')=="aXef"
    assert engine.evaluate("=WEEKDAY(DATE(2026,8,27),2)")==4.0
