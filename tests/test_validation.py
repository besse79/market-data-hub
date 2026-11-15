from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from app.validation import InvalidMarketData, eligible_at, validate_bar, validate_fx

def test_valid_bar():
    assert validate_bar("10", "12", "9", "11", 100)[3] == Decimal("11")

@pytest.mark.parametrize("bar", [
    ("10", "9", "8", "11", 100),
    ("10", "12", "11", "11", 100),
    ("10", "12", "9", "11", -1),
    ("NaN", "12", "9", "11", 100),
    ("10", "Infinity", "9", "11", 100),
    ("10", "12", "9", "11", 1.2),
])
def test_invalid_bars(bar):
    with pytest.raises(InvalidMarketData):
        validate_bar(*bar)

def test_fx_inverse():
    assert Decimal("110") / validate_fx("1.10") == Decimal("1.0E+2")

@pytest.mark.parametrize("rate", ["0", "-1", "NaN", "Infinity", None])
def test_invalid_fx(rate):
    with pytest.raises(InvalidMarketData):
        validate_fx(rate)

def test_point_in_time_late_publication():
    at = datetime(2025, 1, 2, tzinfo=timezone.utc)
    assert not eligible_at(at + timedelta(days=1), at, at)
    assert not eligible_at(at, at + timedelta(days=1), at)
    assert eligible_at(at, at, at)

def test_timezone_required():
    with pytest.raises(InvalidMarketData):
        eligible_at(datetime(2025, 1, 1), datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2025, 1, 2, tzinfo=timezone.utc))
