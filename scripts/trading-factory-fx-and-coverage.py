#!/usr/bin/env python3
"""Yahoo FX research collection and uncovered instrument inventory. No DB writes."""
import argparse,csv,hashlib,json,re,time
from datetime import datetime,timezone,date
from decimal import Decimal
from pathlib import Path
import psycopg
import yfinance as yf

DSN="host=/var/run/postgresql port=5433 dbname=market_data_hub user=benoit"
PAIRS={"CHF":"EURCHF=X","DKK":"EURDKK=X","GBX":"EURGBP=X",
       "NOK":"EURNOK=X","PLN":"EURPLN=X","SEK":"EURSEK=X"}
def collect(pair,start,end):
    df=yf.download(pair,start=start,end=end,auto_adjust=False,actions=False,progress=False,threads=False)
    if df is None or df.empty: raise ValueError("empty response")
    if getattr(df.columns,"nlevels",1)>1:
        if pair in df.columns.get_level_values(-1): df=df.xs(pair,axis=1,level=-1)
        elif pair in df.columns.get_level_values(0): df=df.xs(pair,axis=1,level=0)
        else: raise ValueError("ambiguous Yahoo FX columns")
    if "Close" not in df.columns: raise ValueError("missing Close")
    retrieved=datetime.now(timezone.utc).isoformat()
    obs=[]
    for idx,row in df.iterrows():
        day=idx.date().isoformat()
        rate=Decimal(str(row["Close"]))
        if not rate.is_finite() or rate<=0 or not start<=day<end: raise ValueError("invalid FX rate/session")
        obs.append({"session_date":day,"quote_per_eur":str(rate),
                    "retrieved_at":retrieved,"quality_status":"staged_unverified",
                    "published_at":None,"first_available_at":None,
                    "point_in_time_verified":False,"paper_eligible":False})
    if not obs or len({x["session_date"] for x in obs})!=len(obs): raise ValueError("empty/duplicate FX")
    return obs
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True,type=Path);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    with psycopg.connect(DSN,options="-c default_transaction_read_only=on") as conn:
      with conn.cursor() as cur:
        cur.execute("SELECT current_database(),current_user")
        if cur.fetchone()!=("market_data_hub","benoit"): raise RuntimeError("unexpected DB identity")
        cur.execute("""SELECT i.id::text,i.name,i.asset_type,i.status FROM public.instruments i
          WHERE NOT EXISTS(SELECT 1 FROM public.instrument_identifiers ii
          WHERE ii.instrument_id=i.id AND lower(ii.provider)='yahoo' AND ii.valid_to IS NULL)
          ORDER BY i.name,i.id""")
        missing=cur.fetchall()
        cur.execute("""SELECT currency,count(*) FROM public.instrument_identifiers
          WHERE lower(provider)='yahoo' AND valid_to IS NULL GROUP BY currency""")
        currencies=dict(cur.fetchall())
        cur.execute("SELECT count(*) FROM public.fx_eod"); fx_existing=cur.fetchone()[0]
    with (a.out/"missing-yahoo-identifiers.csv").open("w",newline="",encoding="utf-8") as f:
      w=csv.writer(f);w.writerow(["instrument_id","name","asset_type","status","mapping_status"])
      for row in missing:w.writerow([*row,"MISSING_ACTIVE_YAHOO_IDENTIFIER"])
    unexpected=set(currencies)-set(PAIRS)-{"EUR"}
    if unexpected: raise RuntimeError("unsupported currencies: "+repr(unexpected))
    summary={"unmapped_instruments":len(missing),"currency_counts":currencies,
             "existing_fx_eod":fx_existing,"fx_pairs":{},"errors":{},
             "pit_verified":False,"paper_eligible":False,"db_writes":False}
    start,end="2026-11-17","2026-11-21"
    for quote,pair in PAIRS.items():
      path=a.out/(pair.replace("=","_")+".json")
      try:
        obs=collect(pair,start,end)
        doc={"schema_version":1,"provider":"yahoo","pair":pair,"base":"EUR",
             "quote":"GBP" if quote=="GBX" else quote,
             "quote_units_per_eur":True,"request_start":start,
             "request_end_exclusive":end,"observations":obs,
             "pit_verified":False,"paper_eligible":False}
        path.write_text(json.dumps(doc,indent=2)+"\n",encoding="utf-8")
        summary["fx_pairs"][pair]={"observations":len(obs),"file":str(path)}
      except Exception as e:
        summary["errors"][pair]=str(e)[:300]
      time.sleep(2)
    (a.out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))
    if summary["errors"]: raise SystemExit(3)
if __name__=="__main__":main()
