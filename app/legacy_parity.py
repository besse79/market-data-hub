"""Verify every legacy candle against the original CSV without mutating MKD.

PostgreSQL streams sorted rows using server-side cursor. Numeric comparisons
are exact via Decimal; a SHA256 is emitted for audit evidence.
"""
import argparse
import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from sqlalchemy import text
from app.db import engine

def verify(source: Path):
    digest=hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024),b""):
            digest.update(chunk)
    sql=text("""SELECT m.symbol,m.name,m.currency,b.session_date,
        b.open,b.high,b.low,b.close,b.volume
        FROM eod_bars b JOIN legacy_symbol_map m ON m.instrument_id=b.instrument_id
        WHERE b.provider='yahoo' AND b.quality_status='legacy_unverified'
        ORDER BY m.symbol,b.session_date""")
    count=0
    with engine.connect().execution_options(stream_results=True) as db:
        with source.open(newline="",encoding="utf-8") as handle:
            reader=csv.DictReader(handle)
            with db.execute(sql) as result:
                for row in reader:
                    dbrow=result.fetchone()
                    count+=1
                    if dbrow is None:
                        raise ValueError(f"DB missing row at CSV line {count+1}")
                    symbol,name,currency,day,op,hi,lo,cl,volume=dbrow
                    if (symbol,name,currency,str(day)) != (
                        row["symbol"],row["name"],row["currency"],row["day"]):
                        raise ValueError(f"metadata/date mismatch at CSV line {count+1}")
                    if (Decimal(row["open"]),Decimal(row["high"]),
                        Decimal(row["low"]),Decimal(row["close"]),int(row["volume"])) != (
                        op,hi,lo,cl,volume):
                        raise ValueError(f"OHLCV mismatch at CSV line {count+1}: {symbol} {day}")
                if result.fetchone() is not None:
                    raise ValueError("DB has additional legacy rows")
    return {"status":"verified","compared_bars":count,
            "csv_sha256":digest.hexdigest(),"ohlcv_parity":True}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("csv",type=Path)
    p.add_argument("--report",type=Path)
    a=p.parse_args()
    result=verify(a.csv)
    payload=json.dumps(result,indent=2)+"\n"
    if a.report:
        a.report.write_text(payload,encoding="utf-8")
    print(payload,end="")

if __name__=="__main__":
    main()
