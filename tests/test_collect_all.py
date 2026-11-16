from datetime import date
import pytest
from app.collect_all import collect_all

START = date(2025, 1, 1)
END = date(2025, 2, 1)

def test_batches_cover_all_instruments_without_skips():
    calls = []
    def fake(**kwargs):
        calls.append((kwargs["offset"], kwargs["limit"]))
        return [(str(i), {"created": 1}) for i in range(kwargs["offset"], kwargs["offset"] + kwargs["limit"])]
    result = collect_all(start=START, end=END, count=806, batch_size=100, delay=0, collect=fake)
    assert calls == [(i, min(100, 806-i)) for i in range(0, 806, 100)]
    assert result["expected"] == result["processed"] == 806
    assert result["success"]

def test_failure_is_reported():
    result = collect_all(start=START, end=END, count=1, collect=lambda **_: [("A", {"error": True})])
    assert result["failed"] == ["A"]
    assert not result["success"]

def test_incomplete_batch_fails_closed():
    with pytest.raises(RuntimeError, match="universe changed"):
        collect_all(start=START, end=END, count=2, collect=lambda **_: [])

@pytest.mark.parametrize("kwargs", [
    {"count": 0}, {"batch_size": 0, "count": 1},
    {"delay": -1, "count": 1}, {"start": END, "end": START, "count": 1}
])
def test_invalid_parameters(kwargs):
    args = {"start": START, "end": END, "count": 1, "collect": lambda **_: []}
    args.update(kwargs)
    with pytest.raises(ValueError):
        collect_all(**args)
