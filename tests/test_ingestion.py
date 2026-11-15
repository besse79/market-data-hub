from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
import pytest
from app.ingestion import normalize_bar
from app.validation import InvalidMarketData

def sample():
    at = datetime(2026, 11, 13, 22, tzinfo=timezone.utc)
    return dict(instrument_id=str(uuid4()), session_date="2026-11-13",
                provider="fixture", currency="EUR", open="10.00", high="12.00",
                low="9.00", close="11.00", volume=100,
                published_at=at.isoformat(), first_available_at=at.isoformat())

def test_normalize_valid():
    b = normalize_bar(sample())
    assert b.session_date == date(2026, 11, 13)
    assert b.currency == "EUR"

@pytest.mark.parametrize("key,value", [
    ("high", "8"), ("volume", "-1"), ("currency", "EU"),
    ("provider", ""), ("published_at", "2026-11-13T22:00:00"),
    ("session_date", "2026-11-14"), ("open", "NaN"),
])
def test_invalid_import_rejected(key, value):
    row = sample()
    row[key] = value
    with pytest.raises(InvalidMarketData):
        normalize_bar(row)

def test_no_future_publication():
    row = sample()
    row["published_at"] = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    row["first_available_at"] = row["published_at"]
    with pytest.raises(InvalidMarketData):
        normalize_bar(row)

def test_first_available_after_publication():
    row = sample()
    row["first_available_at"] = "2026-11-13T21:00:00+00:00"
    with pytest.raises(InvalidMarketData):
        normalize_bar(row)
