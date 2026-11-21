#!/usr/bin/env python3
"""Import validated Yahoo research JSON into an isolated PostgreSQL staging table.

Requires externally verified pg_dump backup. Never modifies eod_bars or fx_eod.
All observations remain ineligible for PIT/backtest/PAPER.
"""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import psycopg
from psycopg import sql

DSN="host=/var/run/postgresql port=5433 dbname=market_data_hub user=benoit"

def validate(path):
    raw=path.read_bytes()
    doc=json.loads(raw)
    if doc.get("provider")!="yahoo" or doc.get("schema_version")!=1:
        raise ValueError("unsupported staging document")
    if any(doc.get(k) is not False for k in ("point_in_time_verified","paper_eligible","execution_authorized","backtest_eligible")):
        raise ValueError("staging document attempts eligibility")
    sym=doc["source_symbol"]
    currency=doc["currency"]
    start,end=doc["request_start"],doc["request_end_exclusive"]
    if not doc.get("observations"): raise ValueError("empty observations")
    seen=set()
    entries=[]
    for r in doc["observations"]:
        if r.get("symbol")!=sym.upper() or r.get("currency")!=currency:
            raise ValueError("symbol/currency mismatch")
        if r.get("provider")!="yahoo" or r.get("quality_status")!="staged_unverified":
            raise ValueError("invalid provider/status")
        if r.get("published_at") is not None or r.get("first_available_at") is not None:
            raise ValueError("invented PIT timestamp")
        if any(r.get(k) is not False for k in ("point_in_time_verified","paper_eligible","execution_authorized","backtest_eligible")):
            raise ValueError("observation eligibility violation")
        day=r["session_date"]
        if not start<=day<end or day in seen: raise ValueError("invalid or duplicate session")
        seen.add(day)
        o,h,l,cl,v=[Decimal(str(r[k])) for k in ("open","high","low","close","volume")]
        if not all(x.is_finite() for x in (o,h,l,cl,v)) or min(o,h,l,cl)<=0 or v<0 or v!=v.to_integral_value() or l>min(o,cl) or h<max(o,cl):
            raise ValueError("invalid OHLCV")
        retrieved=datetime.fromisoformat(r["retrieved_at"])
        if retrieved.tzinfo is None: raise ValueError("naive retrieval timestamp")
        entries.append((sym.upper(),currency,day,str(o),str(h),str(l),str(cl),int(v),retrieved,hashlib.sha256(raw).hexdigest()))
    return entries

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--directory",type=Path,required=True)
    p.add_argument("--backup",type=Path,required=True)
    args=p.parse_args()
    if not args.backup.is_file() or args.backup.stat().st_size<1024:
        raise RuntimeError("verified PostgreSQL backup required")
    files=sorted(args.directory.glob("*.json"))
    if not files: raise RuntimeError("no staging JSON files")
    rows=[]
    for file in files: rows.extend(validate(file))
    with psycopg.connect(DSN) as con:
        with con.cursor() as cur:
            cur.execute("SELECT current_database(), current_user")
            if cur.fetchone()!=("market_data_hub","benoit"):
                raise RuntimeError("unexpected DB identity")
            cur.execute("CREATE SCHEMA IF NOT EXISTS mkd_research")
            cur.execute("""CREATE TABLE IF NOT EXISTS mkd_research.yahoo_staging (
                symbol text NOT NULL, currency varchar(3) NOT NULL,
                session_date date NOT NULL, open numeric(24,8) NOT NULL,
                high numeric(24,8) NOT NULL, low numeric(24,8) NOT NULL,
                close numeric(24,8) NOT NULL, volume bigint NOT NULL,
                retrieved_at timestamptz NOT NULL, payload_sha256 char(64) NOT NULL,
                quality_status text NOT NULL DEFAULT 'staged_unverified'
                  CHECK (quality_status='staged_unverified'),
                pit_eligible boolean NOT NULL DEFAULT false CHECK (NOT pit_eligible),
                paper_eligible boolean NOT NULL DEFAULT false CHECK (NOT paper_eligible),
                PRIMARY KEY(symbol,session_date,retrieved_at),
                CHECK (open>0 AND close>0 AND low>0 AND high>=greatest(open,close,low) AND low<=least(open,close) AND volume>=0)
            )""")
            cur.executemany("""INSERT INTO mkd_research.yahoo_staging
               (symbol,currency,session_date,open,high,low,close,volume,retrieved_at,payload_sha256)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (symbol,session_date,retrieved_at) DO NOTHING""",rows)
            cur.execute("SELECT count(*) FROM mkd_research.yahoo_staging")
            count=cur.fetchone()[0]
        con.commit()
    print(json.dumps({"files":len(files),"validated_rows":len(rows),
                      "staging_total_rows":count,"paper_eligible":False,
                      "pit_eligible":False,"legacy_bars_modified":False},indent=2))

if __name__=="__main__":main()
