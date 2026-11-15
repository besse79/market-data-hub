"""Yahoo EOD ingestion into MKD only. No W database access.

Progress is durable per instrument via committed EOD rows; reruns are idempotent.
"""
import argparse
import logging
import time
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import Identifier
from app.ingestion import import_bar
from app.providers.yahoo import yahoo_daily_record

LOG = logging.getLogger(__name__)

def fetch_yahoo(symbol: str, start: date, end: date):
    """Fetch unadjusted daily OHLCV. end is exclusive; caller checks freshness."""
    import yfinance as yf
    frame = yf.Ticker(symbol).history(
        start=start.isoformat(), end=end.isoformat(),
        interval="1d", auto_adjust=False, actions=False,
        raise_errors=True,
    )
    if frame is None or frame.empty:
        return []
    required = {"Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(frame.columns):
        raise ValueError("Yahoo missing OHLCV columns")
    result = []
    for idx, row in frame.iterrows():
        if row[list(required)].isna().any():
            raise ValueError(f"Yahoo incomplete OHLCV {symbol} {idx}")
        result.append((idx.date(), row))
    return result

def collect_one(db: Session, *, instrument_id, symbol: str, currency: str,
                start: date, end: date, dry_run=False, fetch=fetch_yahoo):
    if end <= start:
        raise ValueError("end must be after start")
    if end > datetime.now(timezone.utc).date() + timedelta(days=1):
        raise ValueError("future collection range")
    rows = fetch(symbol, start, end)
    observed_at = datetime.now(timezone.utc)
    stats = {"created": 0, "revised": 0, "unchanged": 0}
    for session_date, row in rows:
        if not start <= session_date < end:
            raise ValueError("provider returned out-of-range candle")
        bar = yahoo_daily_record(
            instrument_id=str(instrument_id), session_date=session_date,
            currency=currency, open=row["Open"], high=row["High"],
            low=row["Low"], close=row["Close"], volume=row["Volume"],
            observed_at=observed_at,
        )
        raw = dict(instrument_id=str(bar.instrument_id), session_date=bar.session_date.isoformat(),
                   provider=bar.provider, currency=bar.currency, open=str(bar.open),
                   high=str(bar.high), low=str(bar.low), close=str(bar.close),
                   volume=bar.volume, published_at=bar.published_at.isoformat(),
                   first_available_at=bar.first_available_at.isoformat())
        stats[import_bar(db, raw, dry_run=dry_run)] += 1
    return stats

def run(*, start: date, end: date, limit: int, dry_run: bool, delay: float, offset: int = 0):
    if limit < 1 or delay < 0 or offset < 0:
        raise ValueError("invalid limit/delay")
    results = []
    with SessionLocal() as db:
        # Only active, currently valid Yahoo identifiers.
        at = datetime.now(timezone.utc)
        ids = db.execute(select(Identifier).where(
            Identifier.provider == "yahoo", Identifier.valid_from <= at,
            (Identifier.valid_to.is_(None) | (Identifier.valid_to > at))
        ).order_by(Identifier.symbol, Identifier.mic, Identifier.id).offset(offset).limit(limit)).scalars().all()
        for ident in ids:
            try:
                # Each instrument is its own transaction/checkpoint.
                # Do not skip older missing dates: replay full requested range safely.
                stats = collect_one(db, instrument_id=ident.instrument_id,
                                    symbol=ident.symbol, currency=ident.currency,
                                    start=start, end=end, dry_run=dry_run)
                if dry_run:
                    db.rollback()
                else:
                    db.commit()
                results.append((ident.symbol, stats))
                LOG.info("collected %s %s", ident.symbol, stats)
            except Exception:
                db.rollback()
                LOG.exception("failed instrument %s; next instrument continues", ident.symbol)
                results.append((ident.symbol, {"error": True}))
            if delay:
                time.sleep(delay)
    return results

def main():
    parser = argparse.ArgumentParser(description="MKD EOD Yahoo ingestion")
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True,
                        help="Exclusive UTC session date")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--offset", type=int, default=0, help="Skip earlier identifiers for deterministic batches")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    result = run(start=args.start, end=args.end, limit=args.limit,
                 delay=args.delay, dry_run=args.dry_run, offset=args.offset)
    if any("error" in stats for _, stats in result):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
