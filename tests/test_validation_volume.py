"""Provider-native integer volumes must survive validation without truncation."""
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from app.ingestion import normalize_bar
from app.validation import InvalidMarketData, validate_bar

def test_python_integer_volume():
    assert validate_bar(1, 2, 1, 2, 1_500_000)[-1] == 1_500_000

def test_numpy_integer_volume():
    np = pytest.importorskip("numpy")
    assert validate_bar(1, 2, 1, 2, np.int64(2_000_000))[-1] == 2_000_000
    assert type(validate_bar(1, 2, 1, 2, np.int64(2_000_000))[-1]) is int

@pytest.mark.parametrize("bad", [True, False, 1.5, 1.0, "12", -1])
def test_fractional_or_noninteger_volume_refused(bad):
    with pytest.raises(InvalidMarketData, match="volume"):
        validate_bar(1, 2, 1, 2, bad)

def test_numpy_volume_ingestion():
    np = pytest.importorskip("numpy")
    at = datetime(2026, 11, 15, 22, tzinfo=timezone.utc).isoformat()
    bar = normalize_bar({
        "instrument_id": str(uuid4()), "session_date": "2026-11-14",
        "provider": "yahoo", "currency": "USD",
        "open": "10", "high": "11", "low": "9", "close": "10",
        "volume": np.int64(2345), "published_at": at, "first_available_at": at,
    })
    assert bar.volume == 2345 and type(bar.volume) is int
