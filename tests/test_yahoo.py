from datetime import date, datetime, timezone, timedelta
from uuid import uuid4
import pytest
from app.providers.yahoo import yahoo_daily_record
from app.validation import InvalidMarketData

def make(**kwargs):
    base = dict(instrument_id=str(uuid4()), session_date=date(2025, 1, 2),
                currency="USD", open=10, high=12, low=9, close=11, volume=123,
                observed_at=datetime(2026, 11, 14, tzinfo=timezone.utc))
    base.update(kwargs)
    return yahoo_daily_record(**base)

def test_historical_yahoo_uses_observation_not_candle_date():
    row = make()
    assert row.first_available_at.year == 2026
    assert row.published_at == row.first_available_at

def test_reject_future_observation():
    with pytest.raises(InvalidMarketData):
        make(observed_at=datetime.now(timezone.utc) + timedelta(days=1))

def test_reject_publication_after_observation():
    with pytest.raises(InvalidMarketData):
        make(published_at=datetime(2026, 11, 15, tzinfo=timezone.utc))
