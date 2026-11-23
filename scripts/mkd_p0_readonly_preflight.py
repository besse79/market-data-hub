"""Read-only P0 readiness check against the MKD PostgreSQL database.

No UPDATE/INSERT/DDL, no Yahoo network calls and no trading authorization.
Use an explicit MKD DSN; never use another application's database.
"""
import argparse
import json
from datetime import datetime, timezone
from sqlalchemy import create_engine, text


def audit(url):
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            db = conn.execute(text("SELECT current_database()")).scalar_one()
            if db != "market_data_hub":
                raise RuntimeError(f"refusing unexpected database: {db}")
            result = conn.execute(text("""
                SELECT quality_status, provider, count(*) AS bars,
                       count(*) FILTER (WHERE published_at IS NULL) AS missing_published,
                       count(*) FILTER (WHERE first_available_at IS NULL) AS missing_available
                FROM eod_bars GROUP BY quality_status, provider
                ORDER BY quality_status, provider
            """)).mappings().all()
            sessions = conn.execute(text("""
                SELECT session_date, count(DISTINCT instrument_id) AS instruments
                FROM eod_bars
                WHERE session_date >= CURRENT_DATE - INTERVAL '14 days'
                GROUP BY session_date ORDER BY session_date DESC
            """)).mappings().all()
            identifiers = conn.execute(text("""
                SELECT count(*) FROM instrument_identifiers
                WHERE provider='yahoo' AND valid_from <= now()
                  AND (valid_to IS NULL OR valid_to > now())
            """)).scalar_one()
            conn.rollback()
        return {
            "audited_at_utc": datetime.now(timezone.utc).isoformat(),
            "database": db,
            "active_yahoo_identifiers": identifiers,
            "provenance": [dict(x) for x in result],
            "recent_sessions": [
                {"session_date": x["session_date"].isoformat(),
                 "instruments": x["instruments"]} for x in sessions
            ],
            "paper_authorized": False,
            "write_authorized": False,
            "reason": "read-only evidence; PIT certification and WSL backup/restore not established",
        }
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.dsn), indent=2))


if __name__ == "__main__":
    main()
