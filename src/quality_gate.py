"""Conservative read-only market-data quality gate."""
from datetime import date
from math import isfinite


def assess_bars(bars: list[dict], as_of: str, currency: str, provenance: str) -> dict:
    reasons = []
    if currency not in {'EUR', 'USD'}: reasons.append('UNSUPPORTED_CURRENCY')
    if provenance != 'point_in_time_verified': reasons.append('UNVERIFIED_PROVENANCE')
    days = []
    for bar in bars:
        try:
            day = date.fromisoformat(bar['day'])
            o, h, l, c, v = (float(bar[k]) for k in ('open','high','low','close','volume'))
            if not all(isfinite(x) for x in (o,h,l,c,v)) or min(o,h,l,c) <= 0 or v < 0 or l > min(o,c) or h < max(o,c):
                reasons.append('INVALID_OHLCV')
            if day > date.fromisoformat(as_of): reasons.append('FUTURE_BAR')
            days.append(day)
        except (KeyError, ValueError, TypeError): reasons.append('INVALID_BAR')
    if len(set(days)) != len(days): reasons.append('DUPLICATE_DAY')
    if not days: reasons.append('EMPTY_HISTORY')
    return {'valid': not reasons, 'reasons': sorted(set(reasons)), 'bar_count': len(bars), 'read_only': True}
