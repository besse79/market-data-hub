"""PostgreSQL-backed integration tests. CI supplies DATABASE_URL and Alembic schema."""
import os
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.ingestion import import_bar
from app.models import Bar, Instrument

@pytest.fixture
def db():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL required for integration tests")
    engine = create_engine(url)
    with engine.connect() as conn:
        trans = conn.begin()
        with Session(bind=conn, join_transaction_mode="create_savepoint") as session:
            yield session
            session.rollback()
        trans.rollback()
    engine.dispose()

def record(i):
    at = datetime(2026, 11, 13, 22, tzinfo=timezone.utc)
    return dict(instrument_id=str(i), session_date="2026-11-13",
                provider="fixture", currency="EUR", open="10", high="12",
                low="9", close="11", volume=100, published_at=at.isoformat(),
                first_available_at=at.isoformat())

def test_import_idempotence_and_revision(db):
    i = uuid4()
    db.add(Instrument(id=i, name="Integration fixture", asset_type="equity", status="active"))
    db.flush()
    row = record(i)
    assert import_bar(db, row) == "created"
    assert import_bar(db, row) == "unchanged"
    row["close"] = "11.5"
    assert import_bar(db, row) == "revised"
    bars = db.scalars(select(Bar).where(Bar.instrument_id == i).order_by(Bar.revision)).all()
    assert [x.revision for x in bars] == [1, 2]
    assert str(bars[0].close) != str(bars[1].close)

def test_import_dry_run_does_not_write(db):
    i = uuid4()
    db.add(Instrument(id=i, name="Dry-run fixture", asset_type="equity", status="active"))
    db.flush()
    assert import_bar(db, record(i), dry_run=True) == "created"
    assert db.scalar(select(Bar).where(Bar.instrument_id == i)) is None

def test_yahoo_observations_remain_unverified_in_postgres(db):
    i = uuid4()
    db.add(Instrument(id=i, name="Yahoo staging fixture", asset_type="equity", status="active"))
    db.flush()
    row = record(i)
    row["provider"] = "yahoo"
    assert import_bar(db, row) == "created"
    saved = db.scalar(select(Bar).where(Bar.instrument_id == i))
    assert saved.quality_status == "staged_unverified"
    assert saved.published_at is not None
    assert saved.first_available_at is not None
    assert import_bar(db, row) == "unchanged"
    assert db.query(Bar).filter(Bar.instrument_id == i).count() == 1


def test_yahoo_revision_does_not_promote_legacy_history(db):
    i = uuid4()
    db.add(Instrument(id=i, name="Legacy staging fixture", asset_type="equity", status="active"))
    db.flush()
    row = record(i)
    row["provider"] = "yahoo"
    db.add(Bar(instrument_id=i, session_date=datetime(2026, 11, 13).date(),
               provider="yahoo", revision=1, currency="EUR",
               open=10, high=12, low=9, close=11, volume=100,
               published_at=None, first_available_at=None,
               ingested_at=datetime.now(timezone.utc), quality_status="legacy_unverified"))
    db.flush()
    row["close"] = "11.5"
    assert import_bar(db, row) == "revised"
    saved = db.scalars(select(Bar).where(Bar.instrument_id == i).order_by(Bar.revision)).all()
    assert [(x.revision, x.quality_status) for x in saved] == [
        (1, "legacy_unverified"), (2, "staged_unverified")]
    assert saved[0].published_at is None
    assert saved[0].first_available_at is None
