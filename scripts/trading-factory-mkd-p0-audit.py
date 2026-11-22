#!/usr/bin/env python3
"""MKD P0: read-only quality audit. No writes, no imports, no migrations.

Requires existing MKD .venv with psycopg. DATABASE_URL is deliberately NOT
used: peer authentication to the already verified local market_data_hub DB.
"""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import psycopg
from mkd_readiness import evaluate_readiness

DSN = "host=/var/run/postgresql port=5433 dbname=market_data_hub user=benoit"


def run(limit: int):
    with psycopg.connect(DSN, options="-c default_transaction_read_only=on") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user")
            assert cur.fetchone() == ("market_data_hub", "benoit"), "Unexpected database identity"
            cur.execute("SELECT quality_status, count(*), min(session_date), max(session_date) FROM public.eod_bars GROUP BY quality_status ORDER BY quality_status")
            quality = [{"status": s, "count": n, "min_session": str(lo), "max_session": str(hi)} for s,n,lo,hi in cur.fetchall()]
            cur.execute("SELECT count(*) FROM public.instruments")
            instruments = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM public.fx_eod")
            fx = cur.fetchone()[0]
            cur.execute("""SELECT count(*) FROM public.eod_bars
                WHERE open <= 0 OR close <= 0 OR high < greatest(open,close,low)
                OR low > least(open,close,high) OR volume < 0""")
            invalid_ohlcv = cur.fetchone()[0]
            cur.execute("""SELECT count(*) FROM public.eod_bars
                WHERE quality_status = 'legacy_unverified'
                AND (published_at IS NOT NULL OR first_available_at IS NOT NULL)""")
            legacy_provenance_violations = cur.fetchone()[0]
            cur.execute("""SELECT count(*) FROM public.eod_bars
                WHERE quality_status = 'valid'
                AND (published_at IS NULL OR first_available_at IS NULL
                     OR first_available_at > now())""")
            invalid_certified = cur.fetchone()[0]
            cur.execute("""SELECT currency, count(*) FROM public.instrument_identifiers
                GROUP BY currency ORDER BY count(*) DESC LIMIT %s""", (limit,))
            currencies = [{"currency": c, "identifiers": n} for c,n in cur.fetchall()]
            cur.execute("""SELECT count(*) FROM public.legacy_symbol_map WHERE NOT mic_verified""")
            mic_unverified = cur.fetchone()[0]
    eligible = sum(row["count"] for row in quality if row["status"] == "valid")
    return {
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": "market_data_hub",
        "instruments": instruments,
        "quality": quality,
        "certified_bars": eligible,
        "fx_rows": fx,
        "invalid_ohlcv": invalid_ohlcv,
        "legacy_provenance_violations": legacy_provenance_violations,
        "invalid_certified": invalid_certified,
        "mic_unverified": mic_unverified,
        "identifier_currencies": currencies,
        **evaluate_readiness(certified_bars=eligible,
            invalid_certified=invalid_certified, invalid_ohlcv=invalid_ohlcv,
            legacy_provenance_violations=legacy_provenance_violations,
            mic_unverified=mic_unverified, fx_rows=fx),
        "fx_ready": fx > 0,
        "action": "NO_GO: collect and verify source provenance, FX and freshness before enabling PAPER"
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be 1..100")
    result = run(args.limit)
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    print(payload)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
