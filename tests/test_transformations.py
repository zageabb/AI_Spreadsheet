from app.services.transformations import TransformationPipeline, TransformationStep


def test_recorded_pipeline_is_deterministic():
    rows = [{"Supplier": "A", "Value": 3}, {"Supplier": "B", "Value": 1}, {"Supplier": "A", "Value": 2}]
    pipeline = TransformationPipeline([
        TransformationStep("filter", {"column": "Supplier", "value": "A"}),
        TransformationStep("sort", {"column": "Value"}),
        TransformationStep("rename", {"mapping": {"Value": "Cost"}}),
    ])
    assert pipeline.apply(rows) == [{"Supplier": "A", "Cost": 2}, {"Supplier": "A", "Cost": 3}]
