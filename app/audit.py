"""Read-only MKD coverage audit. Produces machine-readable evidence, not a parity claim."""
import argparse
import json
from datetime import date
from pathlib import Path
from sqlalchemy import select, func, and_
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
    rows = db.execute(select(Identifier, Instrument, counts.c.sessions,
                             counts.c.first, counts.c.last).join(
        Instrument, Instrument.id == Identifier.instrument_id
    ).outerjoin(counts, counts.c.instrument_id == Identifier.instrument_id).where(
        Identifier.provider == "yahoo", Identifier.valid_to.is_(None)
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

def main():
    parser = argparse.ArgumentParser(description="MKD read-only EOD coverage audit")
    parser.add_argument("--minimum-sessions", type=int, default=1000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with SessionLocal() as db:
        result = coverage(db, minimum_sessions=args.minimum_sessions)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)

if __name__ == "__main__":
    main()
