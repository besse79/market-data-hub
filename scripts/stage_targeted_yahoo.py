#!/usr/bin/env python3
"""Stage missing Yahoo histories for MKD; NEVER writes to PostgreSQL.
Input: W reconciliation report with 267 ABSENT_FROM_MKD_IDENTIFIERS.
Output: validated per-symbol JSONL and manifest in an isolated directory.
Requires: pip install yfinance (outside this script)."""
import argparse, datetime as dt, hashlib, json, math, re, sys, time
from pathlib import Path
from collections import Counter

def main():
    p=argparse.ArgumentParser()
    p.add_argument("reconciliation",type=Path)
    p.add_argument("--output",type=Path,default=Path("/tmp/mkd-targeted-stage"))
    p.add_argument("--limit",type=int,default=267)
    a=p.parse_args()
    if not 1<=a.limit<=267: p.error("limit must be 1..267")
    source=json.loads(a.reconciliation.read_text())
    if source.get("readOnly") is not True or source.get("requested")!=267 or not isinstance(source.get("rows"),list):
        p.error("Unexpected reconciliation report; refuse to collect")
    candidates=[r["symbol"] for r in source["rows"] if r.get("status")=="ABSENT_FROM_MKD_IDENTIFIERS"]
    if len(candidates)!=267 or len(set(candidates))!=267: p.error("Unexpected missing symbols")
    try: import yfinance as yf
    except ImportError: sys.exit("Missing yfinance; install in an isolated Python venv before running")
    a.output.mkdir(parents=True,exist_ok=True)
    if any(a.output.iterdir()): p.error("Output directory must be empty to avoid overwriting data")
    manifest=[]
    start=(dt.date.today()-dt.timedelta(days=365*6)).isoformat()
    end=(dt.date.today()+dt.timedelta(days=1)).isoformat()
    for symbol in candidates[:a.limit]:
        item={"symbol":symbol,"status":"ERROR","rows":0,"source":"yahoo","pit":False}
        try:
            if not re.fullmatch(r"[A-Z0-9.^=\\-]{1,40}",symbol): raise ValueError("Invalid Yahoo symbol")
            df=yf.Ticker(symbol).history(start=start,end=end,interval="1d",auto_adjust=False,actions=False)
            if df is None or df.empty:
                item["status"]="NO_DATA"
            else:
                records=[]; previous=None
                for index,row in df.iterrows():
                    date=index.date().isoformat()
                    vals=[float(row[k]) for k in ("Open","High","Low","Close")]
                    volume=int(row["Volume"])
                    if not all(math.isfinite(v) for v in vals) or min(vals)<=0 or volume<0 or vals[1]<max(vals[0],vals[2],vals[3]) or vals[2]>min(vals[0],vals[1],vals[3]):
                        raise ValueError("Invalid OHLCV")
                    if previous is not None and date<=previous: raise ValueError("Duplicate/out-of-order date")
                    previous=date
                    records.append({"symbol":symbol,"date":date,"open":vals[0],"high":vals[1],"low":vals[2],"close":vals[3],"volume":volume,"provider":"yahoo","quality_status":"legacy_unverified","point_in_time_verified":False})
                # A single symbol cannot exceed 10k daily rows in six years.
                if len(records)>10000: raise ValueError("Unexpected history size")
                filename=hashlib.sha256(symbol.encode()).hexdigest()[:20]+".jsonl"
                payload="".join(json.dumps(r,separators=(",",":"))+"\\n" for r in records)
                (a.output/filename).write_text(payload)
                item.update(status="STAGED",rows=len(records),first=records[0]["date"],last=records[-1]["date"],file=filename,sha256=hashlib.sha256(payload.encode()).hexdigest())
        except Exception as exc:
            item["error"]=str(exc)[:250]
        manifest.append(item)
        print(f"{len(manifest)}/{min(len(candidates),a.limit)} {symbol}: {item['status']} ({item['rows']})",flush=True)
        time.sleep(0.3)
    summary={"createdAt":dt.datetime.now(dt.timezone.utc).isoformat(),"sourceReport":str(a.reconciliation.resolve()),"provider":"yahoo","pit":False,"databaseWrites":0,"requested":a.limit,"counts":dict(Counter(i["status"] for i in manifest)),"instruments":manifest}
    (a.output/"manifest.json").write_text(json.dumps(summary,indent=2)+"\\n")
    print(json.dumps({"manifest":str(a.output/"manifest.json"),"counts":summary["counts"],"databaseWrites":0},indent=2))
    return 2 if any(i["status"]=="ERROR" for i in manifest) else 0
if __name__=="__main__": sys.exit(main())
