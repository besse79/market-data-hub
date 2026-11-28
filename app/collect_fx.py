"""Collect official ECB EUR/USD reference rates, preserving actual observation time."""
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from urllib.request import urlopen
import xml.etree.ElementTree as ET
from sqlalchemy import select, text
from app.db import SessionLocal
from app.models import FxRate

URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"

def parse_rates(payload, today):
    root = ET.fromstring(payload)
    rates = {}
    for node in root.iter():
        if "time" not in node.attrib:
            continue
        day = date.fromisoformat(node.attrib["time"])
        if day > today:
            raise ValueError("future ECB date")
        for child in node:
            if child.get("currency") == "USD":
                rate = Decimal(child.attrib["rate"])
                if not rate.is_finite() or not Decimal("0.1") < rate < Decimal("10") or day in rates:
                    raise ValueError("invalid or duplicate ECB rate")
                rates[day] = rate
    if not rates or max(rates) < today-timedelta(days=5):
        raise ValueError("missing or stale ECB rates")
    return rates

def main():
    with urlopen(URL, timeout=30) as response:
        payload = response.read(2_000_000)
    now = datetime.now(timezone.utc)
    rates = parse_rates(payload, now.date())
    with SessionLocal.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock(810045)"))
        for day, rate in sorted(rates.items()):
            last = db.scalar(select(FxRate).where(FxRate.base=="EUR",FxRate.quote=="USD",FxRate.provider=="ecb",FxRate.effective_date==day).order_by(FxRate.revision.desc()).limit(1))
            if last and last.rate == rate:
                continue
            db.add(FxRate(base="EUR",quote="USD",provider="ecb",effective_date=day,rate=rate,revision=last.revision+1 if last else 1,published_at=now,first_available_at=now,ingested_at=now,quality_status="valid"))
    print("ECB_FX_COLLECTED",len(rates),max(rates),rates[max(rates)])

if __name__ == "__main__":
    main()
