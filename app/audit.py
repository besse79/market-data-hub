"""Read-only MKD coverage audit. Produces machine-readable evidence, not a parity claim."""
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import select, func
from app.db import SessionLocal
from app.models import Bar, Identifier, Instrument

def coverage(db, *, minimum_sessions: int = 1000):
    if minimum_sessions < 1:
        raise ValueError("minimum_sessions must be positive")
    # Count distinct session dates rather than revisions.
    counts = select(Bar.instrument_id.label("instrument_id"),
                    func.count(func.distinct(Bar.session_date)).label("sessions"),
                    func.min(Bar.session_date).label("first"),
                    func.max(Bar.session_date).label("last")).where(
                        Bar.quality_status == "valid", Bar.provider == "yahoo"
                    ).group_by(Bar.instrument_id).subquery()
    at = datetime.now(timezone.utc)
    rows = db.execute(select(Identifier, Instrument, counts.c.sessions,
                             counts.c.first, counts.c.last).join(
        Instrument, Instrument.id == Identifier.instrument_id
    ).outerjoin(counts, counts.c.instrument_id == Identifier.instrument_id).where(
        Identifier.provider == "yahoo", Identifier.valid_from <= at,
        (Identifier.valid_to.is_(None) | (Identifier.valid_to > at))
    ).order_by(Identifier.symbol, Identifier.mic)).all()
    items = []
    for ident, inst, sessions, first, last in rows:
        n = int(sessions or 0)
        items.append({"symbol": ident.symbol, "mic": ident.mic,
                      "currency": ident.currency, "instrument_id": str(inst.id),
                      "sessions": n, "first": first.isoformat() if first else None,
                      "last": last.isoformat() if last else None,
                      "status": "sufficient" if n >= minimum_sessions else
                                ("short" if n else "missing")})
    return {"total": len(items), "sufficient": sum(x["status"] == "sufficient" for x in items),
            "short": sum(x["status"] == "short" for x in items),
            "missing": sum(x["status"] == "missing" for x in items),
            "minimum_sessions": minimum_sessions, "instruments": items}

def reconcile_manifest(report: dict, manifest_rows: list[dict], *, expected: int | None = None):
    """Compare exact symbol/MIC/currency keys without guessing identities."""
    def key(row):
        return (row["symbol"].strip().upper(), row["mic"].strip().upper(),
                row["currency"].strip().upper())
    wanted = [key(row) for row in manifest_rows]
    actual = [key(row) for row in report["instruments"]]
    wanted_set, actual_set = set(wanted), set(actual)
    result = {
        "expected_count": expected,
        "manifest_count": len(wanted),
        "mkd_count": len(actual),
        "duplicates_manifest": len(wanted) - len(wanted_set),
        "duplicates_mkd": len(actual) - len(actual_set),
        "missing_in_mkd": [list(k) for k in sorted(wanted_set - actual_set)],
        "unexpected_in_mkd": [list(k) for k in sorted(actual_set - wanted_set)],
    }
    result["pass"] = (not result["duplicates_manifest"] and not result["duplicates_mkd"]
                      and not result["missing_in_mkd"] and not result["unexpected_in_mkd"]
                      and (expected is None or len(wanted) == expected))
    return result

def main():
    parser = argparse.ArgumentParser(description="MKD read-only EOD coverage audit")
    parser.add_argument("--minimum-sessions", type=int, default=1000)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest", type=Path, help="Independent W CSV for key reconciliation")
    parser.add_argument("--expected", type=int, help="Required count; only with --manifest")
    args = parser.parse_args()
    with SessionLocal() as db:
        result = coverage(db, minimum_sessions=args.minimum_sessions)
    if args.expected is not None and (args.expected < 1 or not args.manifest):
        parser.error("--expected requires --manifest and a positive count")
    if args.manifest:
        from app.universe import parse_manifest
        result["reconciliation"] = reconcile_manifest(result, parse_manifest(args.manifest), expected=args.expected)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    if args.manifest and not result["reconciliation"]["pass"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
