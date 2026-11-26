"""Idempotent, validated EOD ingestion into isolated MKD PostgreSQL.

Source adapters supply normalized records. No connection to consumer databases.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Bar
from app.validation import InvalidMarketData, validate_bar

@dataclass(frozen=True)
class DailyBar:
    instrument_id: UUID
    session_date: date
    provider: str
    currency: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    published_at: datetime
    first_available_at: datetime

def normalize_bar(raw: dict) -> DailyBar:
    try:
        instrument_id = UUID(str(raw["instrument_id"]))
        session_date = date.fromisoformat(str(raw["session_date"]))
        provider = raw["provider"].strip().lower() if isinstance(raw["provider"], str) else ""
        currency = str(raw["currency"]).strip().upper()
        published_at = datetime.fromisoformat(str(raw["published_at"]).replace("Z", "+00:00"))
        first_available_at = datetime.fromisoformat(str(raw["first_available_at"]).replace("Z", "+00:00"))
        open_, high, low, close, volume = validate_bar(
            raw["open"], raw["high"], raw["low"], raw["close"], raw["volume"]
        )
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise InvalidMarketData(f"malformed EOD record: {exc}") from exc
    if not provider or len(provider) > 40 or len(currency) != 3 or not currency.isalpha():
        raise InvalidMarketData("invalid provider or currency")
    if (published_at.tzinfo is None or published_at.utcoffset() is None or
            first_available_at.tzinfo is None or first_available_at.utcoffset() is None):
        raise InvalidMarketData("publication timestamps must have timezone")
    if first_available_at < published_at:
        raise InvalidMarketData("first_available_at precedes publication")
    if session_date > published_at.date():
        raise InvalidMarketData("session date after publication")
    now = datetime.now(timezone.utc)
    if published_at > now:
        raise InvalidMarketData("future publication")
    if first_available_at > now:
        raise InvalidMarketData("future first availability")
    return DailyBar(instrument_id, session_date, provider, currency,
                    open_, high, low, close, volume, published_at, first_available_at)

def import_bar(db: Session, raw: dict, *, dry_run: bool = False) -> str:
    """Import one EOD bar, preserving revisions; caller owns transaction.

    Identical re-imports are no-ops. Corrections append a revision and retain history.
    """
    b = normalize_bar(raw)
    rows = db.scalars(select(Bar).where(
        Bar.instrument_id == b.instrument_id,
        Bar.session_date == b.session_date,
        Bar.provider == b.provider,
    ).order_by(Bar.revision.desc())).all()
    if rows:
        last = rows[0]
        same = (last.currency == b.currency and
                all(Decimal(getattr(last, k)) == getattr(b, k)
                    for k in ("open", "high", "low", "close")) and
                last.volume == b.volume)
        if same:
            return "unchanged"
    if dry_run:
        return "revised" if rows else "created"
    db.add(Bar(
        instrument_id=b.instrument_id, session_date=b.session_date,
        provider=b.provider, revision=rows[0].revision + 1 if rows else 1,
        currency=b.currency, open=b.open, high=b.high, low=b.low,
        close=b.close, volume=b.volume, published_at=b.published_at,
        first_available_at=b.first_available_at, ingested_at=datetime.now(timezone.utc),
        quality_status="staged_unverified" if b.provider == "yahoo" else "valid",
    ))
    db.flush()
    return "revised" if rows else "created"
