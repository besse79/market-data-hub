"""Regression guards for legacy import and point-in-time provenance."""
from pathlib import Path
import pytest
from app.validation import validate_bar, InvalidMarketData

def test_large_volume_supported():
    assert validate_bar("1", "2", "1", "2", 5_000_000_000)[-1] == 5_000_000_000

def test_invalid_ohlcv_rejected():
    with pytest.raises(InvalidMarketData):
        validate_bar("10", "9", "8", "9", 100)

def test_migration_explicitly_blocks_fabricated_dates():
    from app.models import Bar
    constraints = [str(x.sqltext) for x in Bar.__table__.constraints if hasattr(x, "sqltext")]
    assert any("legacy_unverified" in expression and "published_at IS NULL" in expression for expression in constraints)
