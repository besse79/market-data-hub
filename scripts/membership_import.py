"""Import dated membership exports from independent providers without claiming completeness."""
import argparse
import csv
import hashlib
import io
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

def parse_export(raw, day):
    rows=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    if not rows:
        raise ValueError("empty membership export")
    result=[]
    seen=set()
    for row in rows:
        if row["as_of"]!=day.isoformat():
            raise ValueError("membership date mismatch")
        symbol,mic,currency=(row[k].strip() for k in ("symbol","mic","currency"))
        if not symbol or len(mic)!=4 or len(currency)!=3:
            raise ValueError("invalid membership row")
        key=(symbol,mic)
        if key in seen:
            raise ValueError("duplicate listing")
        seen.add(key)
        result.append(dict(symbol=symbol,mic=mic,currency=currency))
    return result

def fetch_export(url, day):
    if urlparse(url).scheme!="https":
        raise ValueError("HTTPS source required")
    with urlopen(url,timeout=30) as response:
        if urlparse(response.geturl()).scheme!="https":
            raise ValueError("insecure redirect")
        raw=response.read(10_000_001)
    if len(raw)>10_000_000:
        raise ValueError("oversized export")
    return parse_export(raw,day),hashlib.sha256(raw).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--day",required=True,type=date.fromisoformat)
    p.add_argument("--sp500-url",required=True)
    p.add_argument("--euronext-url",required=True)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    markets,provenance={},{}
    for market,url in (("SP500",a.sp500_url),("EURONEXT",a.euronext_url)):
        markets[market],digest=fetch_export(url,a.day)
        provenance[market]={"url":url,"sha256":digest}
    if len(markets["SP500"])<500:
        raise ValueError("incomplete S&P 500 export")
    payload={"as_of":a.day.isoformat(),"markets":markets,"provenance":provenance,"membership_verified":False}
    with a.output.open("x") as f:
        json.dump(payload,f,indent=2,allow_nan=False)

if __name__=="__main__":
    main()
