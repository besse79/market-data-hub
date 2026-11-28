#!/usr/bin/env python3
"""Qualify staged Yahoo symbols using live Yahoo metadata; no database writes."""
import argparse,json,re,time,datetime,collections
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument("stage",type=Path)
p.add_argument("--output",type=Path,required=True)
a=p.parse_args()
import yfinance as yf
m=json.loads((a.stage/"manifest.json").read_text())
assert len(m["instruments"])==266 and m["pit"] is False
# Explicit suffix/exchange/currency triplets. Exchange code is checked against Yahoo metadata.
markets={
 ".L":("XLON",{"LSE","LON"},{"GBp","GBX","GBP"}),
 ".OL":("XOSL",{"OSL"},{"NOK"}),
 ".SW":("XSWX",{"EBS","SWX"},{"CHF"}),
 ".ST":("XSTO",{"STO"},{"SEK"}),
 ".CO":("XCSE",{"CPH"},{"DKK"}),
 ".HE":("XHEL",{"HEL"},{"EUR"}),
 ".WA":("XWAR",{"WSE","WAR"},{"PLN"})
}
results=[]
for n,item in enumerate(m["instruments"],1):
 symbol=item["symbol"]; errors=[]
 try:
  info=yf.Ticker(symbol).info
  name=str(info.get("longName") or info.get("shortName") or "").strip()
  currency=str(info.get("currency") or "").strip()
  exchange=str(info.get("exchange") or "").strip().upper()
  quote=str(info.get("symbol") or "").strip().upper()
  suffix=next((s for s in markets if symbol.endswith(s)),None)
  if suffix is None:errors.append("UNSUPPORTED_MARKET")
  else:
   mic,exchanges,currencies=markets[suffix]
   if exchange not in exchanges:errors.append("EXCHANGE_MISMATCH")
   if currency not in currencies:errors.append("CURRENCY_MISMATCH")
  if quote!=symbol:errors.append("SYMBOL_MISMATCH")
  if not name or len(name)>250:errors.append("NAME_MISSING")
  # GBP pence is not GBP. Preserve Yahoo's quoted unit as GBX.
  if currency in ("GBp","GBX"):currency="GBX"
  if currency=="GBP" and suffix==".L":errors.append("GBP_UNIT_REQUIRES_REVIEW")
  if not re.fullmatch("[A-Z]{3}",currency):errors.append("CURRENCY_INVALID")
  result={"symbol":symbol,"name":name,"currency":currency,"exchange":exchange,
          "mic":mic if suffix else None,"bars":item["rows"],"status":"QUALIFIED" if not errors else "BLOCKED","issues":errors}
 except Exception as exc:
  result={"symbol":symbol,"status":"BLOCKED","issues":["YAHOO_METADATA_ERROR"],"error":str(exc)[:180]}
 results.append(result)
 print(f"{n}/266 {symbol}: {result['status']} {','.join(result['issues'])}",flush=True)
 time.sleep(0.2)
report={"createdAt":datetime.datetime.now(datetime.timezone.utc).isoformat(),"stage":str(a.stage.resolve()),
        "stageManifestSha256":__import__("hashlib").sha256((a.stage/"manifest.json").read_bytes()).hexdigest(),
        "source":"Yahoo Finance live metadata","pointInTime":False,"instruments":results,
        "counts":dict(collections.Counter(x["status"] for x in results))}
if a.output.exists():raise SystemExit("Refuse overwrite")
a.output.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({"report":str(a.output),"counts":report["counts"]},indent=2))
