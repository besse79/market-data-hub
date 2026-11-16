import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, BigInteger, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Instrument(Base):
    __tablename__ = "instruments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(250))
    asset_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="active")

class Identifier(Base):
    __tablename__ = "instrument_identifiers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("instruments.id"))
    provider: Mapped[str] = mapped_column(String(40))
    symbol: Mapped[str] = mapped_column(String(80))
    mic: Mapped[str] = mapped_column(String(10))
    currency: Mapped[str] = mapped_column(String(3))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="identifier_dates"),)

class Bar(Base):
    __tablename__ = "eod_bars"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("instruments.id"))
    session_date: Mapped[datetime] = mapped_column(Date)
    provider: Mapped[str] = mapped_column(String(40))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    currency: Mapped[str] = mapped_column(String(3))
    open: Mapped[float] = mapped_column(Numeric(24, 8))
    high: Mapped[float] = mapped_column(Numeric(24, 8))
    low: Mapped[float] = mapped_column(Numeric(24, 8))
    close: Mapped[float] = mapped_column(Numeric(24, 8))
    volume: Mapped[int] = mapped_column(BigInteger)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    first_available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    quality_status: Mapped[str] = mapped_column(String(20), default="valid")
    __table_args__ = (
        UniqueConstraint("instrument_id", "session_date", "provider", "revision", name="uq_bar_revision"),
        CheckConstraint("high >= open AND high >= close AND high >= low AND low <= open AND low <= close AND low >= 0 AND volume >= 0", name="valid_ohlcv"),
    )

class FxRate(Base):
    __tablename__ = "fx_eod"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    base: Mapped[str] = mapped_column(String(3))
    quote: Mapped[str] = mapped_column(String(3))
    effective_date: Mapped[datetime] = mapped_column(Date)
    rate: Mapped[float] = mapped_column(Numeric(24, 12))
    provider: Mapped[str] = mapped_column(String(40))
    revision: Mapped[int] = mapped_column(Integer)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    first_available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    quality_status: Mapped[str] = mapped_column(String(20), default="valid")
    __table_args__ = (
        UniqueConstraint("base", "quote", "effective_date", "provider", "revision", name="uq_fx_revision"),
        CheckConstraint("rate > 0 AND base <> quote", name="valid_fx"),
    )
