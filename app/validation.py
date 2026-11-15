"""Pure validation helpers shared by ingestion and API adapters."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

class InvalidMarketData(ValueError):
    pass

def decimal(value, name):
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise InvalidMarketData(f"{name}: not numeric") from None
    if not n.is_finite():
        raise InvalidMarketData(f"{name}: non-finite")
    return n

def validate_bar(open_, high, low, close, volume):
    o, h, l, c = (decimal(x, k) for x, k in ((open_, "open"), (high, "high"), (low, "low"), (close, "close")))
    if l < 0 or h < max(o, c, l) or l > min(o, c) or min(o, c) < 0:
        raise InvalidMarketData("inconsistent OHLC")
    if isinstance(volume, bool) or not isinstance(volume, int) or volume < 0:
        raise InvalidMarketData("invalid volume")
    return o, h, l, c, volume

def validate_fx(rate, base="EUR", quote="USD"):
    if base == quote or len(base) != 3 or len(quote) != 3:
        raise InvalidMarketData("invalid FX pair")
    n = decimal(rate, "rate")
    if n <= 0:
        raise InvalidMarketData("FX rate must be positive")
    return n

def eligible_at(published_at: datetime, first_available_at: datetime, as_of: datetime) -> bool:
    values = (published_at, first_available_at, as_of)
    if any(v.tzinfo is None or v.utcoffset() is None for v in values):
        raise InvalidMarketData("timestamps must be timezone-aware")
    if as_of > datetime.now(timezone.utc):
        raise InvalidMarketData("future as_of")
    return max(published_at, first_available_at) <= as_of
