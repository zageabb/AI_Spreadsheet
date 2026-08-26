from app.engine.calculation_service import WorkbookCalculationService
from app.engine.formula_engine import FormulaEngine
from app.formulas.registry import register_builtin_functions
from app.models.workbook import Workbook


def _service():
    workbook = Workbook(name="Test")
    sales = workbook.add_sheet("Sales Data")
    summary = workbook.add_sheet("Summary")
    engine = FormulaEngine(); register_builtin_functions(engine)
    return workbook, sales, summary, WorkbookCalculationService(workbook, engine)


def test_cross_sheet_range_and_downstream_recalculation():
    workbook, sales, summary, service = _service()
    sales.get_cell("A1").value = 10
    sales.get_cell("A2").value = 20
    summary.get_cell("A1").formula = "=SUM('Sales Data'!A1:A2)"
    summary.get_cell("B1").formula = "=A1*2"
    service.recalculate()
    assert summary.get_cell("A1").value == 30.0
    assert summary.get_cell("B1").value == 60.0

    sales.get_cell("A2").value = 25
    service.recalculate({service.cell_key("Sales Data", "A2")})
    assert summary.get_cell("A1").value == 35.0
    assert summary.get_cell("B1").value == 70.0


def test_circular_reference_returns_spreadsheet_error():
    _workbook, _sales, summary, service = _service()
    summary.get_cell("A1").formula = "=B1"
    summary.get_cell("B1").formula = "=A1"
    service.recalculate()
    assert summary.get_cell("A1").value == "#CIRC!"
    assert summary.get_cell("B1").value == "#CIRC!"
