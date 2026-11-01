import pytest
from pydantic import ValidationError
from app.schemas import EntryCreate


@pytest.mark.parametrize("kwargs", [
    {"metric_type": "exercise"},
    {"metric_type": "exercise", "metric_data": {}},
    {"metric_type": "exercise", "metric_data": {"name": "  "}},
    {"metric_type": "weight"},
    {"metric_type": " ", "metric_data": {"value": 1}},
    {"metric_data": {"value": 1}},
])
def test_invalid_metric_rejected(kwargs):
    with pytest.raises(ValidationError):
        EntryCreate(**kwargs)


@pytest.mark.parametrize("kwargs", [
    {"prose": "hi"},
    {"metric_type": "exercise", "metric_data": {"name": "squat"}},
    {"metric_type": "weight", "metric_data": {"value": 80}},
])
def test_valid_entries_accepted(kwargs):
    EntryCreate(**kwargs)
