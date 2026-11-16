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
