#!/usr/bin/env python3
"""Read-only coverage and provenance report for MarketDataHub.

Never certifies legacy observations or writes to PostgreSQL.
"""
import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg

DSN = "host=/var/run/postgresql port=5433 dbname=market_data_hub user=benoit"


def assess_coverage(rows, *, as_of, expected_min=1):
    """Summarize per-session counts without assuming every asset trades every day."""
    if not isinstance(as_of, date) or isinstance(as_of, datetime):
        raise ValueError("as_of must be a date")
    if type(expected_min) is not int or expected_min < 1:
        raise ValueError("expected_min must be positive")
    result = []
    seen = set()
    for day, instruments, bars in rows:
        if not isinstance(day, date) or isinstance(day, datetime) or day > as_of:
            raise ValueError("invalid session date")
        if day in seen:
            raise ValueError("duplicate session")
        seen.add(day)
        if type(instruments) is not int or type(bars) is not int or instruments < 0 or bars < instruments:
            raise ValueError("invalid coverage counts")
        result.append({"session_date": day.isoformat(), "instruments": instruments,
                       "bars": bars, "below_expected_min": instruments < expected_min})
    result.sort(key=lambda r: r["session_date"])
    return {"sessions": result, "latest_session": result[-1]["session_date"] if result else None,
            "has_recent_coverage": bool(result and result[-1]["instruments"] >= expected_min),
            "paper_authorized": False, "pit_verified": False}


def run(*, days, expected_min):
    if not 1 <= days <= 90:
        raise ValueError("days must be 1..90")
    as_of = datetime.now(timezone.utc).date()
    with psycopg.connect(DSN, options="-c default_transaction_read_only=on") as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        with conn.cursor() as cur:
            cur.execute("""SELECT current_database(), current_user, current_setting('port'),
                                  current_setting('transaction_read_only'),
                                  current_setting('transaction_isolation')""")
            if cur.fetchone() != ("market_data_hub", "benoit", "5433", "on", "repeatable read"):
                raise RuntimeError("unexpected database or transaction mode")
            cur.execute("""SELECT session_date, count(DISTINCT instrument_id)::int, count(*)::int
                           FROM public.eod_bars
                           WHERE session_date >= current_date - %s
                           AND session_date <= current_date
                           GROUP BY session_date ORDER BY session_date""", (days,))
            rows = cur.fetchall()
            cur.execute("""SELECT quality_status, provider, count(*)::bigint,
                                  count(*) FILTER (WHERE published_at IS NULL)::bigint,
                                  count(*) FILTER (WHERE first_available_at IS NULL)::bigint
                           FROM public.eod_bars
                           GROUP BY quality_status, provider ORDER BY quality_status, provider""")
            provenance = [{"quality_status": status, "provider": provider, "bars": n,
                           "missing_published_at": missing_pub, "missing_first_available_at": missing_first}
                          for status, provider, n, missing_pub, missing_first in cur.fetchall()]
    coverage = assess_coverage(rows, as_of=as_of, expected_min=expected_min)
    return {"audited_at_utc": datetime.now(timezone.utc).isoformat(),
            "database": "market_data_hub", "lookback_days": days,
            "expected_min_instruments_per_session": expected_min,
            **coverage, "provenance": provenance,
            "note": "A low count may reflect holidays or instrument calendars; investigate before backfill.",
            "action": "NO_GO: audit provenance, session calendars, benchmarks and freshness before PAPER"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--expected-min", type=int, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(days=args.days, expected_min=args.expected_min)
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    print(payload)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
