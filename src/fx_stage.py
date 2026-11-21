"""Fail-closed FX staging for Yahoo close prices; never certify historical PIT.

Yahoo pairs are quote units per one base unit, e.g. EURUSD=X means USD per EUR.
GBX is pence and is normalized via GBP with a 1/100 unit factor.
"""
from datetime import datetime, timezone, date
from decimal import Decimal, InvalidOperation

PAIRS = {
    "USD": "EURUSD=X", "GBP": "EURGBP=X", "CHF": "EURCHF=X",
    "SEK": "EURSEK=X", "NOK": "EURNOK=X", "DKK": "EURDKK=X",
    "PLN": "EURPLN=X", "CAD": "EURCAD=X", "JPY": "EURJPY=X",
    "AUD": "EURAUD=X",
}
SUPPORTED = set(PAIRS) | {"EUR", "GBX"}


def fx_requirement(currency):
    currency = currency.upper()
    if currency not in SUPPORTED:
        raise ValueError("unsupported currency")
    if currency == "EUR":
        return {"pair": None, "unit_multiplier": "1", "currency": "EUR"}
    if currency == "GBX":
        return {"pair": PAIRS["GBP"], "unit_multiplier": "0.01", "currency": "GBX"}
    return {"pair": PAIRS[currency], "unit_multiplier": "1", "currency": currency}


def stage_fx(base, quote, session_date, close, retrieved_at):
    if base != "EUR" or quote not in PAIRS:
        raise ValueError("unsupported FX pair")
    day = date.fromisoformat(str(session_date))
    if retrieved_at.tzinfo is None or retrieved_at > datetime.now(timezone.utc) or day > retrieved_at.date():
        raise ValueError("invalid FX timestamps")
    try:
        rate = Decimal(str(close))
    except (InvalidOperation, TypeError):
        raise ValueError("invalid FX rate") from None
    if not rate.is_finite() or rate <= 0:
        raise ValueError("invalid FX rate")
    return {
        "base": base, "quote": quote, "session_date": day.isoformat(),
        "quote_per_eur": str(rate), "provider": "yahoo",
        "retrieved_at": retrieved_at.isoformat(),
        "published_at": None, "first_available_at": None,
        "quality_status": "staged_unverified", "point_in_time_verified": False,
        "paper_eligible": False, "backtest_eligible": False,
    }


def convert_to_eur(amount, currency, quote_per_eur):
    info = fx_requirement(currency)
    value = Decimal(str(amount)) * Decimal(info["unit_multiplier"])
    if info["pair"] is None:
        return value
    if quote_per_eur is None:
        raise ValueError("FX missing: fail closed")
    rate = Decimal(str(quote_per_eur))
    if not rate.is_finite() or rate <= 0:
        raise ValueError("invalid FX rate")
    return value / rate
