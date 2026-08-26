from app.models.sheet import Worksheet
from app.services.transformations import (TransformationPipeline, TransformationStep,
    rows_to_worksheet, worksheet_to_rows)


def test_recorded_pipeline_is_deterministic():
    rows = [{"Supplier": "A", "Value": 3}, {"Supplier": "B", "Value": 1}, {"Supplier": "A", "Value": 2}]
    pipeline = TransformationPipeline([
        TransformationStep("filter", {"column": "Supplier", "value": "A"}),
        TransformationStep("sort", {"column": "Value"}),
        TransformationStep("rename", {"mapping": {"Value": "Cost"}}),
    ])
    assert pipeline.apply(rows) == [{"Supplier": "A", "Cost": 2}, {"Supplier": "A", "Cost": 3}]


def test_rows_round_trip_through_worksheet():
    rows = [{"Supplier": "A", "Cost": 2}, {"Supplier": "B", "Cost": None}]
    sheet = Worksheet(name="Data")
    rows_to_worksheet(rows, sheet)
    assert worksheet_to_rows(sheet) == rows
    assert sheet.metadata["transformation_columns"] == ["Supplier", "Cost"]


def test_pipeline_can_be_recreated_from_saved_metadata():
    payload = [{"operation": "filter", "parameters": {"column": "Value", "operator": "gt", "value": 1}}]
    pipeline = TransformationPipeline.from_dicts(payload)
    assert pipeline.apply([{"Value": 1}, {"Value": 2}]) == [{"Value": 2}]
