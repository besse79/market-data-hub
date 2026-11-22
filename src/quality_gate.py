"""Fail-closed, read-only market-data quality gate for EUR/USD daily OHLCV."""
from datetime import date
from math import isfinite


def assess_bars(bars: list[dict], as_of: str, currency: str, provenance: str) -> dict:
    """Validate bars without changing their order, content, or storage.

    The caller must supply independently verified point-in-time provenance.
    This gate cannot itself certify provenance or provider freshness.
    """
    reasons: set[str] = set()
    if currency not in {"EUR", "USD"}:
        reasons.add("UNSUPPORTED_CURRENCY")
    if provenance != "point_in_time_verified":
        reasons.add("UNVERIFIED_PROVENANCE")
    try:
        cutoff = date.fromisoformat(as_of)
    except (TypeError, ValueError):
        cutoff = None
        reasons.add("INVALID_AS_OF")

    if not isinstance(bars, list):
        return {"valid": False, "reasons": sorted(reasons | {"INVALID_HISTORY"}),
                "bar_count": 0, "read_only": True}

    days: list[date] = []
    for bar in bars:
        if not isinstance(bar, dict):
            reasons.add("INVALID_BAR")
            continue
        try:
            day = date.fromisoformat(bar["day"])
            values = [float(bar[k]) for k in ("open", "high", "low", "close", "volume")]
            o, h, low, close, volume = values
            if (not all(isfinite(v) for v in values)
                    or min(o, h, low, close) <= 0 or volume < 0
                    or low > min(o, close) or h < max(o, close)
                    or low > h):
                reasons.add("INVALID_OHLCV")
            if cutoff is not None and day > cutoff:
                reasons.add("FUTURE_BAR")
            days.append(day)
        except (KeyError, ValueError, TypeError, OverflowError):
            reasons.add("INVALID_BAR")

    if len(set(days)) != len(days):
        reasons.add("DUPLICATE_DAY")
    if days != sorted(days):
        reasons.add("UNSORTED_HISTORY")
    if not days:
        reasons.add("EMPTY_HISTORY")
    return {"valid": not reasons, "reasons": sorted(reasons),
            "bar_count": len(bars), "read_only": True}
