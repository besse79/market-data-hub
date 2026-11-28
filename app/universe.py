"""Non-destructive MKD universe import from an explicit CSV manifest.

Never reads or writes Weinstein'S database. Identifiers are matched on
(provider, symbol, mic) at the current instant; collisions fail closed.
"""
import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import Identifier, Instrument

REQUIRED = {"symbol", "mic", "currency", "name", "asset_type"}
def parse_manifest(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
            raise ValueError(f"manifest missing required columns: {sorted(REQUIRED)}")
        rows = []
        seen = set()
        for number, raw in enumerate(reader, 2):
            row = {k: (raw.get(k) or "").strip() for k in REQUIRED}
            row["symbol"] = row["symbol"].upper()
            row["mic"] = row["mic"].upper()
            row["currency"] = row["currency"].upper()
            if any(not v for v in row.values()):
                raise ValueError(f"blank field on CSV line {number}")
            if len(row["symbol"]) > 80 or len(row["mic"]) > 10 or len(row["currency"]) != 3:
                raise ValueError(f"invalid identifier on CSV line {number}")
            key = ("yahoo", row["symbol"], row["mic"])
            if key in seen:
                raise ValueError(f"duplicate identifier on CSV line {number}: {key}")
            seen.add(key)
            rows.append(row)
    if not rows:
        raise ValueError("empty manifest")
    return rows

def import_universe(db: Session, rows: list[dict], *, dry_run: bool = False):
    now = datetime.now(timezone.utc)
    result = {"created": 0, "unchanged": 0, "conflict": 0}
    for row in rows:
        matches = db.scalars(select(Identifier).where(
            Identifier.provider == "yahoo",
            Identifier.symbol == row["symbol"], Identifier.mic == row["mic"],
            Identifier.valid_from <= now,
            (Identifier.valid_to.is_(None) | (Identifier.valid_to > now))
        )).all()
        if len(matches) > 1:
            raise ValueError(f"ambiguous active identifier: {row['symbol']} / {row['mic']}")
        if matches:
            ident = matches[0]
            instrument = db.get(Instrument, ident.instrument_id)
            if not instrument or ident.currency != row["currency"] or instrument.name != row["name"] or instrument.asset_type != row["asset_type"]:
                raise ValueError(f"conflicting instrument metadata: {row['symbol']} / {row['mic']}")
            result["unchanged"] += 1
            continue
        result["created"] += 1
        if not dry_run:
            instrument = Instrument(id=uuid4(), name=row["name"], asset_type=row["asset_type"], status="active")
            db.add(instrument)
            db.flush()
            db.add(Identifier(instrument_id=instrument.id, provider="yahoo",
                              symbol=row["symbol"], mic=row["mic"],
                              currency=row["currency"], valid_from=now, valid_to=None))
            db.flush()
    return result

def trading_universe(rows):
    """Preserve historical imports; restrict new Trading Factory imports to EUR/USD equities."""
    selected = [r for r in rows if r["currency"] in {"EUR", "USD"} and r["asset_type"].lower() in {"equity", "stock"}]
    if not selected:
        raise ValueError("empty EUR/USD equity universe")
    return selected

def main():
    parser = argparse.ArgumentParser(description="Import MKD instruments from explicit manifest")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--apply", action="store_true", help="Write to MKD (default is dry-run)")
    parser.add_argument("--trading-factory", action="store_true", help="Restrict import to EUR/USD equities")
    args = parser.parse_args()
    rows = parse_manifest(args.manifest)
    if args.trading_factory:
        rows = trading_universe(rows)
    with SessionLocal.begin() as db:
        result = import_universe(db, rows, dry_run=not args.apply)
        print(result)

if __name__ == "__main__":
    main()
