"""Fail-closed EOD batch orchestration for the complete MKD Yahoo universe.

Only invokes MKD collector. No connection to W is made.
"""
import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from sqlalchemy import select, func
from app.db import SessionLocal
from app.models import Identifier
from app.collector import run

def collect_all(*, start: date, end: date, batch_size: int = 100,
                delay: float = 1.0, dry_run: bool = False, collect=run,
                count=None):
    if batch_size < 1 or delay < 0 or end <= start:
        raise ValueError("invalid collection parameters")
    if count is None:
        with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            count = db.scalar(select(func.count()).select_from(Identifier).where(
                Identifier.provider == "yahoo", Identifier.currency.in_(("EUR", "USD")), Identifier.valid_from <= now,
                (Identifier.valid_to.is_(None) | (Identifier.valid_to > now))
            ))
    if not isinstance(count, int) or count < 1:
        raise ValueError("no Yahoo identifiers available")
    results = []
    for offset in range(0, count, batch_size):
        expected = min(batch_size, count - offset)
        batch = collect(start=start, end=end, limit=expected,
                        offset=offset, delay=delay, dry_run=dry_run)
        if len(batch) != expected:
            raise RuntimeError(f"universe changed during collection at offset {offset}: expected {expected}, got {len(batch)}")
        results.extend(batch)
    failed = [symbol for symbol, stats in results if "error" in stats]
    return {"expected": count, "processed": len(results),
            "failed": failed, "success": not failed, "dry_run": dry_run,
            "start": start.isoformat(), "end_exclusive": end.isoformat()}

def main():
    parser = argparse.ArgumentParser(description="Collect full MKD Yahoo EOD universe")
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = collect_all(start=args.start, end=args.end,
                         batch_size=args.batch_size, delay=args.delay,
                         dry_run=args.dry_run)
    payload = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if not result["success"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
