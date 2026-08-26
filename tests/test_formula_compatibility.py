from datetime import date

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
