from datetime import date, datetime, timezone
from uuid import UUID
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import Bar, FxRate, Identifier, Instrument

app = FastAPI(title="MarketDataHub", version="0.1.0")

def session():
    with SessionLocal() as db:
        yield db

def cutoff(as_of: datetime) -> datetime:
    if as_of.tzinfo is None:
        raise HTTPException(422, "as_of must contain timezone")
    if as_of > datetime.now(timezone.utc):
        raise HTTPException(422, "future as_of forbidden")
    return as_of

@app.get("/health/live")
def live():
    return {"status": "ok"}

@app.get("/v1/instruments")
def instruments(symbol: str, mic: str, as_of: datetime, db: Session = Depends(session)):
    at = cutoff(as_of)
    rows = db.execute(select(Instrument, Identifier).join(Identifier).where(
        Identifier.symbol == symbol, Identifier.mic == mic,
        Identifier.valid_from <= at,
        (Identifier.valid_to.is_(None) | (Identifier.valid_to > at))
    ).limit(2)).all()
    if not rows:
        raise HTTPException(404, "instrument not found")
    if len(rows) != 1:
        raise HTTPException(409, "ambiguous instrument")
    inst, ident = rows[0]
    return {"instrument_id": inst.id, "name": inst.name, "symbol": ident.symbol, "mic": ident.mic, "currency": ident.currency}

@app.get("/v1/bars")
def bars(instrument_id: UUID, start: date, end: date, as_of: datetime,
         limit: int = Query(500, ge=1, le=1000), provider: str | None = None, db: Session = Depends(session)):
    at = cutoff(as_of)
    if end < start or end > at.date():
        raise HTTPException(422, "invalid date range")
    if provider is None:
        raise HTTPException(422, "provider required to prevent ambiguous multi-source bars")
    latest = select(Bar.instrument_id, Bar.session_date, Bar.provider, func.max(Bar.revision).label("revision")).where(
        Bar.published_at <= at, Bar.first_available_at <= at
    ).group_by(Bar.instrument_id, Bar.session_date, Bar.provider).subquery()
    rows = db.scalars(select(Bar).join(latest, and_(
        Bar.instrument_id == latest.c.instrument_id, Bar.session_date == latest.c.session_date,
        Bar.provider == latest.c.provider, Bar.revision == latest.c.revision
    )).where(
        Bar.instrument_id == instrument_id, Bar.provider == provider, Bar.session_date >= start, Bar.session_date <= end,
        Bar.published_at <= at, Bar.first_available_at <= at, Bar.quality_status == "valid"
    ).order_by(Bar.session_date, Bar.provider, Bar.revision.desc()).limit(limit + 1)).all()
    if not rows:
        raise HTTPException(404, "no certified bars at as_of")
    if len(rows) > limit:
        raise HTTPException(422, "result exceeds limit; narrow date range")
    return {"instrument_id": instrument_id, "as_of": at, "items": [
        {"date": r.session_date, "open": r.open, "high": r.high, "low": r.low,
         "close": r.close, "volume": r.volume, "currency": r.currency,
         "provider": r.provider, "revision": r.revision, "published_at": r.published_at,
         "first_available_at": r.first_available_at} for r in rows]}

@app.get("/v1/fx")
def fx(base: str, quote: str, date: date, as_of: datetime, db: Session = Depends(session)):
    at = cutoff(as_of)
    if base != "EUR" or quote != "USD" or date > at.date():
        raise HTTPException(422, "unsupported pair or future date")
    latest_fx = select(FxRate.base, FxRate.quote, FxRate.effective_date, FxRate.provider,
                       func.max(FxRate.revision).label("revision")).where(
        FxRate.published_at <= at, FxRate.first_available_at <= at
    ).group_by(FxRate.base, FxRate.quote, FxRate.effective_date, FxRate.provider).subquery()
    rows = db.scalars(select(FxRate).join(latest_fx, and_(
        FxRate.base == latest_fx.c.base, FxRate.quote == latest_fx.c.quote,
        FxRate.effective_date == latest_fx.c.effective_date,
        FxRate.provider == latest_fx.c.provider, FxRate.revision == latest_fx.c.revision
    )).where(
        FxRate.base == base, FxRate.quote == quote, FxRate.effective_date == date,
        FxRate.published_at <= at, FxRate.first_available_at <= at,
        FxRate.quality_status == "valid"
    ).order_by(FxRate.revision.desc()).limit(2)).all()
    if not rows:
        raise HTTPException(404, "no certified FX at as_of")
    if len(rows) > 1:
        raise HTTPException(409, "ambiguous FX provider")
    r = rows[0]
    return {"base": base, "quote": quote, "effective_date": date, "rate": r.rate,
            "provider": r.provider, "revision": r.revision,
            "published_at": r.published_at, "first_available_at": r.first_available_at}

@app.get("/v1/legacy/bars")
def legacy_bars(instrument_id: UUID, start: date, end: date,
                limit: int = Query(500, ge=1, le=1000),
                db: Session = Depends(session)):
    """Explicitly non-PIT research data. Never use for as-of backtests."""
    if end < start:
        raise HTTPException(422, "invalid date range")
    rows = db.scalars(select(Bar).where(
        Bar.instrument_id == instrument_id,
        Bar.session_date >= start,
        Bar.session_date <= end,
        Bar.provider == "yahoo",
        Bar.quality_status == "legacy_unverified",
        Bar.published_at.is_(None),
        Bar.first_available_at.is_(None),
    ).order_by(Bar.session_date, Bar.revision.desc()).limit(limit + 1)).all()
    if len(rows) > limit:
        raise HTTPException(422, "result exceeds limit; narrow date range")
    return {"instrument_id": instrument_id, "point_in_time_verified": False,
            "backtest_eligible": False, "items": [
                {"date": r.session_date, "open": r.open, "high": r.high,
                 "low": r.low, "close": r.close, "volume": r.volume,
                 "currency": r.currency, "provider": r.provider,
                 "quality_status": r.quality_status}
                for r in rows]}

@app.get("/v1/legacy/resolve")
def legacy_resolve(symbol: str, db: Session = Depends(session)):
    """Resolve Yahoo source symbols without claiming a verified exchange MIC."""
    from sqlalchemy import text
    row = db.execute(text("""SELECT symbol, name, currency, instrument_id,
        mic, mic_verified FROM legacy_symbol_map WHERE symbol = :symbol"""),
        {"symbol": symbol.strip().upper()}).mappings().first()
    if row is None:
        raise HTTPException(404, "legacy symbol not found")
    return dict(row)
