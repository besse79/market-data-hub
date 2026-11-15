import csv
import pytest
from app.universe import parse_manifest

def test_manifest(tmp_path):
    p = tmp_path / "universe.csv"
    p.write_text("symbol,mic,currency,name,asset_type\nAAPL,XNAS,USD,Apple,equity\n", encoding="utf-8")
    rows = parse_manifest(p)
    assert rows[0]["symbol"] == "AAPL"

def test_duplicate_manifest_rejected(tmp_path):
    p = tmp_path / "universe.csv"
    p.write_text("symbol,mic,currency,name,asset_type\nAAPL,XNAS,USD,Apple,equity\naapl,XNAS,USD,Apple,equity\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        parse_manifest(p)

def test_blank_manifest_rejected(tmp_path):
    p = tmp_path / "universe.csv"
    p.write_text("symbol,mic,currency,name,asset_type\n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        parse_manifest(p)
