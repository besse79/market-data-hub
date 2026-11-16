"""Normalize daily Yahoo Finance candles without fabricating publication timestamps.

Yahoo's historical candles do not establish when a record was first available.
The ingestion caller MUST provide independently recorded availability metadata.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from app.ingestion import normalize_bar
from app.validation import InvalidMarketData

def yahoo_daily_record(*, instrument_id: str, session_date: date,
                       currency: str, open, high, low, close, volume,
                       observed_at: datetime, published_at: datetime | None = None):
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise InvalidMarketData("observed_at must be timezone-aware")
    if observed_at > datetime.now(timezone.utc):
        raise InvalidMarketData("future observed_at")
    if published_at is None:
        # Do not infer historical publication time from a candle date.
        published_at = observed_at
    if published_at.tzinfo is None or published_at.utcoffset() is None:
        raise InvalidMarketData("published_at must be timezone-aware")
    if published_at > observed_at:
        raise InvalidMarketData("published_at after observation")
    return normalize_bar(dict(
        instrument_id=instrument_id, session_date=session_date.isoformat(),
        provider="yahoo", currency=currency, open=str(Decimal(str(open))),
        high=str(Decimal(str(high))), low=str(Decimal(str(low))),
        close=str(Decimal(str(close))), volume=volume,
        published_at=published_at.isoformat(),
        first_available_at=observed_at.isoformat(),
    ))
