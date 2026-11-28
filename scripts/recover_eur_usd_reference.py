"""Recover existing EUR/USD identifiers using current Yahoo exchange metadata."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, text
from app.backup import backup

EXCHANGES = {"NMS":"XNAS","NGM":"XNAS","NCM":"XNAS","NYQ":"XNYS","ASE":"XASE",
             "PAR":"XPAR","AMS":"XAMS","BRU":"XBRU","LIS":"XLIS","DUB":"XDUB",
             "HEL":"XHEL","MIL":"XMIL","GER":"XETR","MCE":"XMAD","VIE":"XWBO","ISE":"XDUB","ATH":"XATH","BTS":"BATS"}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup", type=Path)
    args = p.parse_args()
    url = os.environ["DATABASE_URL"]
    engine = create_engine(url)
    with engine.connect() as c:
        if c.execute(text("select current_database()")).scalar_one() != "market_data_hub":
            raise ValueError("unexpected database")
        rows = c.execute(text("""
          SELECT DISTINCT m.instrument_id,m.symbol,m.currency
          FROM legacy_symbol_map m
          WHERE m.currency IN ('EUR','USD')
          AND EXISTS (SELECT 1 FROM eod_bars b WHERE b.instrument_id=m.instrument_id
                      AND b.currency=m.currency AND b.provider='yahoo')
          AND NOT EXISTS (SELECT 1 FROM instrument_identifiers i
                          WHERE i.instrument_id=m.instrument_id AND i.provider='yahoo'
                          AND i.valid_to IS NULL)
          ORDER BY m.symbol
        """)).mappings().all()
    evidence = {}
    source = Path.home() / 'market-data-hub/evidence/yahoo-reference-recovery.jsonl'
    for line in source.read_text().splitlines():
        item = json.loads(line)
        observed = datetime.fromisoformat(item['observed_at'])
        age = (datetime.now(timezone.utc)-observed).total_seconds()
        if not 0 <= age <= 86400 or EXCHANGES.get(item['exchange']) != item['mic']:
            raise ValueError('stale or invalid reference evidence')
        key = (item['symbol'],item['currency'],item['instrument_id'])
        if key in evidence and evidence[key] != item['mic']:
            raise ValueError('conflicting evidence')
        evidence[key] = item['mic']
    approved, rejected = [], []
    for row in rows:
        try:
            mic = evidence.get((row["symbol"],row["currency"],str(row["instrument_id"])))
            if not mic:
                raise ValueError("missing verified evidence")
            approved.append(dict(row, mic=mic))
        except Exception as exc:
            rejected.append({"symbol":row["symbol"],"reason":type(exc).__name__})
    print(json.dumps({"approved":len(approved),"rejected":rejected},default=str),flush=True)
    if not args.apply:
        return
    if not args.backup:
        p.error("--apply requires --backup")
    if {r["symbol"] for r in rejected} != {"CPG.L","IHG.L","EXSA.DE","SPY"} or len(approved) != 800:
        raise ValueError("unexpected recovery coverage; refusing write")
    print(backup(destination=args.backup,database_url=url),flush=True)
    with engine.begin() as c:
        c.execute(text("LOCK TABLE instrument_identifiers IN SHARE ROW EXCLUSIVE MODE"))
        for row in approved:
            conflict = c.execute(text("""SELECT count(*) FROM instrument_identifiers
                WHERE provider='yahoo' AND valid_to IS NULL AND
                (instrument_id=:instrument_id OR (symbol=:symbol AND mic=:mic))"""),row).scalar_one()
            if conflict:
                raise ValueError("concurrent identifier or collision")
            c.execute(text("""INSERT INTO instrument_identifiers
                (instrument_id,provider,symbol,mic,currency,valid_from,valid_to)
                VALUES (:instrument_id,'yahoo',:symbol,:mic,:currency,:now,NULL)"""),
                dict(row,now=datetime.now(timezone.utc)))
    print(json.dumps({"inserted":len(approved),"unresolved":len(rejected)}))

if __name__ == "__main__":
    main()
