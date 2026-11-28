"""Read-only audit of Yahoo identifier coverage and EOD gaps.

Produces actionable evidence without assuming missing market sessions are trading days.
Never writes to PostgreSQL, changes identifiers or authorizes PAPER.
"""
import argparse
import json
from datetime import date, datetime, timezone
from sqlalchemy import create_engine, text


def classify(instruments, active_identifiers, rows):
    """Pure summary; multiple active identifiers are flagged rather than silently selected."""
    counts = {}
    for row in rows:
        counts[row["instrument_id"]] = counts.get(row["instrument_id"], 0) + 1
    return {
        "instruments": instruments,
        "active_yahoo_identifiers": active_identifiers,
        "instruments_with_active_yahoo": len(counts),
        "instruments_without_active_yahoo": instruments - len(counts),
        "instruments_with_multiple_active_yahoo": sum(v > 1 for v in counts.values()),
        "identifier_count_not_instrument_count": active_identifiers != len(counts),
        "collection_universe_complete": instruments > 0 and instruments == len(counts)
            and all(v == 1 for v in counts.values()),
        "paper_authorized": False,
    }


def audit(dsn, since):
    engine = create_engine(dsn)
    try:
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            name = conn.execute(text("SELECT current_database()")).scalar_one()
            if name != "market_data_hub":
                raise RuntimeError(f"unexpected database: {name}")
            instruments = conn.execute(text("SELECT count(*) FROM instruments")).scalar_one()
            ids = [dict(x) for x in conn.execute(text("""
                SELECT instrument_id::text AS instrument_id, symbol, mic, currency
                FROM instrument_identifiers
                WHERE provider='yahoo' AND valid_from <= now()
                  AND (valid_to IS NULL OR valid_to > now())
                ORDER BY instrument_id, symbol, mic
            """)).mappings()]
            covered = {x["instrument_id"] for x in ids}
            absent = [dict(x) for x in conn.execute(text("""
                SELECT i.id::text AS instrument_id, i.name, i.asset_type, i.status
                FROM instruments i WHERE NOT EXISTS (
                    SELECT 1 FROM instrument_identifiers x
                    WHERE x.instrument_id=i.id AND x.provider='yahoo'
                      AND x.valid_from <= now()
                      AND (x.valid_to IS NULL OR x.valid_to > now())
                ) ORDER BY i.name, i.id
            """)).mappings()]
            sessions = [dict(x) for x in conn.execute(text("""
                SELECT b.session_date, count(DISTINCT b.instrument_id) AS instruments
                FROM eod_bars b WHERE b.session_date >= :since
                GROUP BY b.session_date ORDER BY b.session_date
            """), {"since": since}).mappings()]
            per_instrument = [dict(x) for x in conn.execute(text("""
                SELECT x.instrument_id::text AS instrument_id, x.symbol, x.mic,
                       max(b.session_date) AS latest_session,
                       count(DISTINCT b.session_date) FILTER
                         (WHERE b.session_date >= :since) AS sessions_since
                FROM instrument_identifiers x
                LEFT JOIN eod_bars b ON b.instrument_id=x.instrument_id AND b.provider='yahoo'
                WHERE x.provider='yahoo' AND x.valid_from <= now()
                  AND (x.valid_to IS NULL OR x.valid_to > now())
                GROUP BY x.instrument_id, x.symbol, x.mic
                ORDER BY x.symbol, x.mic
            """), {"since": since}).mappings()]
            conn.rollback()
        summary = classify(instruments, len(ids), ids)
        return {
            "database": name,
            "audited_at_utc": datetime.now(timezone.utc).isoformat(),
            "since": since.isoformat(),
            "summary": summary,
            "missing_active_yahoo": absent,
            "active_identifiers": ids,
            "session_coverage": [
                {"date": x["session_date"].isoformat(), "instruments": x["instruments"]}
                for x in sessions
            ],
            "active_identifier_last_sessions": [
                {**x, "latest_session": x["latest_session"].isoformat()
                 if x["latest_session"] else None} for x in per_instrument
            ],
            "write_authorized": False,
            "note": "No calendar inferred; verify exchanges and provider mapping before repair.",
        }
    finally:
        engine.dispose()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dsn", required=True)
    p.add_argument("--since", type=date.fromisoformat, default=date(2026, 11, 13))
    p.add_argument("--output")
    args = p.parse_args()
    result = audit(args.dsn, args.since)
    data = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(data + "\n", encoding="utf-8")
        print(json.dumps({"output": args.output, "summary": result["summary"],
                          "session_coverage": result["session_coverage"]}, indent=2))
    else:
        print(data)


if __name__ == "__main__":
    main()
