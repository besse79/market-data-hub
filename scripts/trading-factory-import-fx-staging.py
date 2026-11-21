#!/usr/bin/env python3
"""Fail-closed import of Yahoo FX research JSON into isolated PostgreSQL staging."""
import argparse,hashlib,json
from pathlib import Path
from datetime import datetime,date
from decimal import Decimal
import psycopg

DSN="host=/var/run/postgresql port=5433 dbname=market_data_hub user=benoit"
PAIRS={"EURCHF=X":"CHF","EURDKK=X":"DKK","EURGBP=X":"GBP",
       "EURNOK=X":"NOK","EURPLN=X":"PLN","EURSEK=X":"SEK"}
def parse_file(path):
    raw=path.read_bytes(); d=json.loads(raw)
    pair=d.get("pair")
    if (d.get("schema_version")!=1 or d.get("provider")!="yahoo"
        or pair not in PAIRS or d.get("base")!="EUR" or d.get("quote")!=PAIRS[pair]
        or d.get("quote_units_per_eur") is not True
        or d.get("pit_verified") is not False or d.get("paper_eligible") is not False):
        raise ValueError(f"invalid FX document: {path}")
    start,end=date.fromisoformat(d["request_start"]),date.fromisoformat(d["request_end_exclusive"])
    obs=d.get("observations")
    if not isinstance(obs,list) or not obs: raise ValueError("missing FX observations")
    rows=[]; seen=set()
    for r in obs:
        day=date.fromisoformat(r["session_date"])
        rate=Decimal(str(r["quote_per_eur"]))
        ts=datetime.fromisoformat(r["retrieved_at"])
        if (day<start or day>=end or day in seen or not rate.is_finite() or rate<=0
            or ts.tzinfo is None or r.get("quality_status")!="staged_unverified"
            or r.get("published_at") is not None or r.get("first_available_at") is not None
            or r.get("point_in_time_verified") is not False or r.get("paper_eligible") is not False):
            raise ValueError(f"invalid FX observation: {path}")
        seen.add(day)
        rows.append((pair,"EUR",PAIRS[pair],day,rate,ts,hashlib.sha256(raw).hexdigest()))
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument("--directory",type=Path,required=True)
    p.add_argument("--backup",type=Path,required=True);a=p.parse_args()
    if not a.backup.is_file() or a.backup.stat().st_size<1024:
        raise RuntimeError("backup required")
    files=sorted(a.directory.glob("EUR*_X.json"))
    if len(files)!=len(PAIRS): raise RuntimeError("expected exactly six FX documents")
    rows=[]; observed=set()
    for f in files:
        rr=parse_file(f)
        if rr[0][0] in observed: raise RuntimeError("duplicate FX pair")
        observed.add(rr[0][0]);rows+=rr
    if observed!=set(PAIRS): raise RuntimeError("missing FX pairs")
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(),current_user")
            if cur.fetchone()!=("market_data_hub","benoit"): raise RuntimeError("wrong database")
            cur.execute("CREATE SCHEMA IF NOT EXISTS mkd_research")
            cur.execute("""CREATE TABLE IF NOT EXISTS mkd_research.fx_staging(
              pair text NOT NULL,base varchar(3) NOT NULL CHECK(base='EUR'),
              quote varchar(3) NOT NULL,session_date date NOT NULL,
              quote_per_eur numeric(24,12) NOT NULL CHECK(quote_per_eur>0),
              retrieved_at timestamptz NOT NULL,payload_sha256 char(64) NOT NULL,
              quality_status text NOT NULL DEFAULT 'staged_unverified' CHECK(quality_status='staged_unverified'),
              pit_eligible boolean NOT NULL DEFAULT false CHECK(NOT pit_eligible),
              paper_eligible boolean NOT NULL DEFAULT false CHECK(NOT paper_eligible),
              PRIMARY KEY(pair,session_date,retrieved_at))""")
            cur.executemany("""INSERT INTO mkd_research.fx_staging
               (pair,base,quote,session_date,quote_per_eur,retrieved_at,payload_sha256)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT(pair,session_date,retrieved_at) DO NOTHING""",rows)
            cur.execute("SELECT count(*) FROM mkd_research.fx_staging")
            total=cur.fetchone()[0]
        conn.commit()
    print(json.dumps({"files":len(files),"validated_observations":len(rows),
       "staging_total":total,"pit_eligible":False,"paper_eligible":False,
       "fx_eod_modified":False},indent=2))
if __name__=="__main__":main()
