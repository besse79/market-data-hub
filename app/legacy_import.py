"""Import Weinstein EOD candles from an exported CSV, never from the live source DB.

CSV columns: symbol,name,currency,day,open,high,low,close,volume.
Identifiers must already exist in MKD, with provider=yahoo and an unambiguous
symbol/currency match. Unknown or ambiguous identifiers fail closed.
No fabricated historical publication/availability timestamps.
"""
import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from app.db import SessionLocal
from app.models import Bar, Identifier
from app.validation import validate_bar, InvalidMarketData

REQUIRED = {"symbol", "name", "currency", "day", "open", "high", "low", "close", "volume"}
BATCH = 2000

def import_legacy(path: Path, *, apply: bool = False):
    counts = Counter()
    unresolved = Counter()
    with SessionLocal() as db:
        identifiers = db.execute(select(Identifier.symbol, Identifier.currency, Identifier.instrument_id).where(
            Identifier.provider == "yahoo", Identifier.valid_to.is_(None)
        )).all()
        by_key = {}
        for symbol, currency, instrument_id in identifiers:
            by_key.setdefault((symbol, currency), set()).add(instrument_id)
        # Preflight entire source before writing any row.
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
                raise ValueError("CSV missing required fields")
            previous_key = None
            for line, row in enumerate(reader, 2):
                symbol = row["symbol"].strip().upper()
                currency = row["currency"].strip().upper()
                key = (symbol, row["day"])
                if previous_key is not None and key <= previous_key:
                    raise ValueError(f"unsorted or duplicate source bar on line {line}: {key}")
                previous_key = key
                matches = by_key.get((symbol, currency), set())
                if len(matches) != 1:
                    unresolved[(symbol, currency)] += 1
                try:
                    from datetime import date
                    date.fromisoformat(row["day"])
                    validate_bar(row["open"], row["high"], row["low"], row["close"], int(row["volume"]))
                except (ValueError, InvalidMarketData) as exc:
                    raise ValueError(f"invalid OHLCV on line {line}: {exc}") from exc
                counts["source_bars"] += 1
        counts["unresolved_bars"] = sum(unresolved.values())
        counts["unresolved_symbols"] = len(unresolved)
        if unresolved:
            return {"status": "blocked_unresolved_identifiers", "counts": dict(counts),
                    "unresolved": [{"symbol": s, "currency": c, "bars": n}
                                   for (s, c), n in sorted(unresolved.items())]}
        if not apply:
            return {"status": "dry_run", "counts": dict(counts)}
        # One transaction, no partial imports on failure.
        now = datetime.now(timezone.utc)
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    symbol, currency = row["symbol"].strip().upper(), row["currency"].strip().upper()
                    instrument_id = next(iter(by_key[(symbol, currency)]))
                    from datetime import date
                    day = date.fromisoformat(row["day"])
                    o, h, l, c, volume = validate_bar(
                        row["open"], row["high"], row["low"], row["close"], int(row["volume"]))
                    existing = db.scalars(select(Bar).where(
                        Bar.instrument_id == instrument_id, Bar.session_date == day,
                        Bar.provider == "yahoo").order_by(Bar.revision.desc()).limit(1)).first()
                    if existing:
                        if (existing.currency == currency and
                            (existing.open, existing.high, existing.low, existing.close) == (o, h, l, c)
                            and existing.volume == volume):
                            counts["unchanged"] += 1
                            continue
                        raise ValueError(f"conflicting existing bar: {symbol} {day}; no silent revisions")
                    db.add(Bar(instrument_id=instrument_id, session_date=day,
                               provider="yahoo", revision=1, currency=currency,
                               open=o, high=h, low=l, close=c, volume=volume,
                               published_at=None, first_available_at=None,
                               ingested_at=now, quality_status="legacy_unverified"))
                    counts["created"] += 1
                    if counts["created"] % BATCH == 0:
                        db.flush()
            db.commit()
        except BaseException:
            db.rollback()
            raise
        return {"status": "applied", "counts": dict(counts)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = import_legacy(args.csv, apply=args.apply)
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.report:
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if result["status"] == "blocked_unresolved_identifiers":
        raise SystemExit(2)

if __name__ == "__main__":
    main()
