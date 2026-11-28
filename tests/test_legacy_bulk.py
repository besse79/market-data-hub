"""Fast legacy import guards (no DB needed)."""
import csv
import pytest
from app.legacy_bulk import migrate, EXPECTED

def test_bulk_rejects_wrong_csv_header(tmp_path):
    path=tmp_path/"bad.csv"
    path.write_text("symbol,day\nAAPL,2026-01-01\n")
    with pytest.raises(ValueError, match="CSV columns"):
        migrate(path)

def test_bulk_expected_columns():
    assert EXPECTED == ("symbol","name","currency","day","open","high","low","close","volume")
