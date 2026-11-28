#!/usr/bin/env python3
"""Persist and verify the 266 staged Yahoo histories. No database writes."""
import argparse,hashlib,json,os,shutil,sys
from pathlib import Path
from collections import Counter
p=argparse.ArgumentParser()
p.add_argument("--first",type=Path,required=True)
p.add_argument("--retry",type=Path,required=True)
p.add_argument("--destination",type=Path,required=True)
a=p.parse_args()
if a.destination.exists():sys.exit("Destination exists; refusing overwrite")
sources=[]
for path in (a.first,a.retry):
 m=json.loads((path/"manifest.json").read_text())
 if m.get("databaseWrites")!=0 or m.get("provider")!="yahoo" or m.get("pit") is not False:sys.exit("Invalid source manifest")
 sources.append((path,m))
items=[x for path,m in sources for x in m["instruments"] if x["status"]=="STAGED"]
symbols=[x["symbol"] for x in items]
if len(items)!=266 or len(set(symbols))!=266:sys.exit("Expected 266 distinct staged instruments")
a.destination.mkdir(parents=True,mode=0o700)
try:
 out=[]
 for path,m in sources:
  for item in m["instruments"]:
   if item["status"]!="STAGED":continue
   for field,digest in (("file","sha256"),("quarantineFile","quarantineSha256")):
    if field not in item:continue
    f=path/item[field]
    if f.name!=item[field] or not f.is_file() or f.is_symlink():raise ValueError("Invalid staged file")
    data=f.read_bytes()
    if hashlib.sha256(data).hexdigest()!=item[digest]:raise ValueError("SHA mismatch: "+str(f))
    target=a.destination/f.name
    if target.exists():raise ValueError("Filename collision")
    target.write_bytes(data)
    if hashlib.sha256(target.read_bytes()).hexdigest()!=item[digest]:raise ValueError("Copy verification failed")
   # Verify actual OHLCV rows and counts, not only hashes
   lines=(a.destination/item["file"]).read_text().splitlines()
   if len(lines)!=item["rows"]:raise ValueError("Row count mismatch")
   previous=""
   for line in lines:
    r=json.loads(line)
    if r.get("symbol")!=item["symbol"] or r.get("date","")<=previous or r.get("quality_status")!="legacy_unverified" or r.get("point_in_time_verified") is not False:
     raise ValueError("Invalid staged provenance or ordering")
    previous=r["date"]
   out.append(item)
 manifest={"provider":"yahoo","pit":False,"databaseWrites":0,"instruments":out,"counts":dict(Counter(x["status"] for x in out)),"sources":[str(a.first),str(a.retry)]}
 (a.destination/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
 print(json.dumps({"persistent":str(a.destination),"verifiedInstruments":len(out),"bars":sum(x["rows"] for x in out),"quarantined":sum(x.get("rejected",0) for x in out),"databaseWrites":0},indent=2))
except Exception:
 shutil.rmtree(a.destination)
 raise
