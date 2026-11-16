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

from app.audit import reconcile_manifest

def test_manifest_reconciliation_exact_keys():
    report = {"instruments": [{"symbol": "AAPL", "mic": "XNAS", "currency": "USD"}]}
    rows = [{"symbol": "aapl", "mic": "xnas", "currency": "usd"}]
    assert reconcile_manifest(report, rows, expected=1)["pass"]

def test_manifest_reconciliation_rejects_missing_extra_and_duplicates():
    report = {"instruments": [{"symbol": "AAPL", "mic": "XNAS", "currency": "USD"},
                              {"symbol": "AAPL", "mic": "XNAS", "currency": "USD"}]}
    rows = [{"symbol": "AAPL", "mic": "XNYS", "currency": "USD"}]
    result = reconcile_manifest(report, rows, expected=806)
    assert not result["pass"]
    assert result["duplicates_mkd"] == 1
    assert result["missing_in_mkd"] == [["AAPL", "XNYS", "USD"]]
    assert result["unexpected_in_mkd"] == [["AAPL", "XNAS", "USD"]]

def test_manifest_reconciliation_rejects_wrong_expected_count():
    report = {"instruments": [{"symbol": "AAPL", "mic": "XNAS", "currency": "USD"}]}
    rows = [{"symbol": "AAPL", "mic": "XNAS", "currency": "USD"}]
    assert not reconcile_manifest(report, rows, expected=806)["pass"]
