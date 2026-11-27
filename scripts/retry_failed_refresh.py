"""Retry failed symbols only; preserve successful instrument checkpoints."""
import argparse
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Identifier
from app.collector import collect_one

def main():
    p = argparse.ArgumentParser()
    p.add_argument("report", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    report = json.loads(args.report.read_text())
    failed = report["failed"]
    if report["expected"] != 802 or report["processed"] != 802 or report["dry_run"] or not failed or len(set(failed)) != len(failed):
        raise ValueError("unexpected refresh evidence")
    start, end = date.fromisoformat(report["start"]), date.fromisoformat(report["end_exclusive"])
    remaining = []
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        ids = db.execute(select(Identifier).where(Identifier.provider == "yahoo", Identifier.currency.in_(("EUR", "USD")), Identifier.valid_from <= now, (Identifier.valid_to.is_(None) | (Identifier.valid_to > now)), Identifier.symbol.in_(failed))).scalars().all()
        mapping = {i.symbol: (i.instrument_id, i.currency) for i in ids}
        if len(ids) != len(failed) or set(mapping) != set(failed):
            raise ValueError("failed symbol mapping ambiguous")
        for symbol in failed:
            instrument_id, currency = mapping[symbol]
            try:
                stats = collect_one(db, instrument_id=instrument_id, symbol=symbol, currency=currency, start=start, end=end)
                db.commit()
                print(symbol, stats, flush=True)
            except Exception as exc:
                db.rollback()
                remaining.append(symbol)
                print(symbol, type(exc).__name__, str(exc), flush=True)
            time.sleep(3)
    result = {**report, "failed": remaining, "success": not remaining, "retried": len(failed)}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if remaining:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
