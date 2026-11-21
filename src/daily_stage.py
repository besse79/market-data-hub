"""Fail-closed Yahoo daily observation staging; no DB writes or PIT certification.

A download timestamp is NOT the provider's publication timestamp. Data from
this module is always research-only until independently verified.
"""
from __future__ import annotations
from datetime import datetime, timezone, date
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any


def validate_observation(row: dict[str, Any], *, symbol: str, currency: str,
                         retrieved_at: datetime, as_of: datetime | None = None) -> dict:
    if retrieved_at.tzinfo is None:
        raise ValueError("retrieved_at must be timezone-aware")
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None or retrieved_at > now:
        raise ValueError("invalid retrieval timestamp")
    day = date.fromisoformat(str(row["session_date"]))
    if day > retrieved_at.date():
        raise ValueError("future session date")
    values = {}
    for key in ("open", "high", "low", "close", "volume"):
        try:
            value = Decimal(str(row[key]))
        except (InvalidOperation, KeyError, TypeError):
            raise ValueError(f"invalid {key}") from None
        if not value.is_finite():
            raise ValueError(f"nonfinite {key}")
        values[key] = value
    o,h,l,c,v = (values[k] for k in ("open","high","low","close","volume"))
    if min(o,h,l,c) <= 0 or v < 0 or v != v.to_integral_value() or l > min(o,c) or h < max(o,c) or h < l:
        raise ValueError("invalid OHLCV")
    if not symbol.strip() or not currency.strip() or len(currency.strip()) != 3:
        raise ValueError("invalid symbol/currency")
    return {
        "symbol": symbol.strip().upper(),
        "currency": currency.strip().upper(),
        "session_date": day.isoformat(),
        **{k: str(values[k]) for k in ("open","high","low","close","volume")},
        "provider": "yahoo",
        "retrieved_at": retrieved_at.isoformat(),
        "published_at": None,
        "first_available_at": None,
        "mic_verified": False,
        "quality_status": "staged_unverified",
        "point_in_time_verified": False,
        "backtest_eligible": False,
        "paper_eligible": False,
        "execution_authorized": False,
    }


def stage_batch(rows: list[dict], *, symbol: str, currency: str,
                retrieved_at: datetime, as_of: datetime | None = None) -> list[dict]:
    """Reject the ENTIRE batch on duplicate, invalid or future data."""
    result = [validate_observation(r, symbol=symbol, currency=currency,
                                   retrieved_at=retrieved_at, as_of=as_of) for r in rows]
    dates = [r["session_date"] for r in result]
    if len(set(dates)) != len(dates):
        raise ValueError("duplicate sessions")
    if not result:
        raise ValueError("empty batch")
    return sorted(result, key=lambda r: r["session_date"])
