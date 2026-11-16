import json
import pytest
from app.parity import compare

def fixtures(tmp_path, w="symbol,mic,currency\nAAPL,XNAS,USD\n", rows=None):
    manifest = tmp_path / "w.csv"
    manifest.write_text(w)
    coverage = tmp_path / "coverage.json"
    if rows is None:
        rows = [{"symbol": "AAPL", "mic": "XNAS", "currency": "USD", "status": "sufficient"}]
    coverage.write_text(json.dumps({"instruments": rows}))
    return manifest, coverage

def test_parity_complete_but_not_ohlcv(tmp_path):
    result = compare(*fixtures(tmp_path))
    assert result["identifier_parity"] and result["coverage_complete"]
    assert result["ohlcv_parity_verified"] is False

def test_missing_extra_currency_and_short(tmp_path):
    rows = [{"symbol": "AAPL", "mic": "XNAS", "currency": "EUR", "status": "short"},
            {"symbol": "MSFT", "mic": "XNAS", "currency": "USD", "status": "sufficient"}]
    result = compare(*fixtures(tmp_path, rows=rows))
    assert result["extra_in_mkd"] == [["MSFT", "XNAS"]]
    assert result["currency_mismatches"] == [["AAPL", "XNAS"]]
    assert result["insufficient_history"] == [["AAPL", "XNAS"]]
    assert not result["identifier_parity"]

def test_duplicate_w_refused(tmp_path):
    with pytest.raises(ValueError, match="duplicate W"):
        compare(*fixtures(tmp_path, w="symbol,mic,currency\nAAPL,XNAS,USD\nAAPL,XNAS,USD\n"))

def test_duplicate_mkd_refused(tmp_path):
    rows = [{"symbol": "AAPL", "mic": "XNAS", "currency": "USD", "status": "sufficient"}] * 2
    with pytest.raises(ValueError, match="duplicate MKD"):
        compare(*fixtures(tmp_path, rows=rows))
