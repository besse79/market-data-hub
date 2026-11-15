from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from app.audit import coverage

def test_coverage_counts_unique_sessions():
    db = Mock()
    inst = SimpleNamespace(id="id1")
    ident = SimpleNamespace(symbol="AAPL", mic="XNAS", currency="USD")
    db.execute.return_value.all.return_value = [(ident, inst, 1050, None, None)]
    result = coverage(db, minimum_sessions=1000)
    assert result["total"] == 1
    assert result["sufficient"] == 1
    assert result["short"] == 0

def test_empty_coverage():
    db = Mock()
    db.execute.return_value.all.return_value = []
    assert coverage(db)["total"] == 0

def test_invalid_threshold():
    with pytest.raises(ValueError):
        coverage(Mock(), minimum_sessions=0)
