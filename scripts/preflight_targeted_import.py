#!/usr/bin/env python3
"""Preflight 266 staged instruments before MKD import. Fail closed; read-only."""
import argparse,collections,hashlib,json,re,sys
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument("stage",type=Path)
p.add_argument("--output",type=Path)
a=p.parse_args()
m=json.loads((a.stage/"manifest.json").read_text())
items=m.get("instruments",[])
if len(items)!=266 or len({x["symbol"] for x in items})!=266 or m.get("pit") is not False or m.get("databaseWrites")!=0:
 sys.exit("Stage contract invalid")
# No guessed MICs. Symbol suffix is only a hint for validation.
suffixes={".L":"LONDON",".OL":"OSLO",".SW":"SWISS",".ST":"STOCKHOLM",".CO":"COPENHAGEN",".WA":"WARSAW",".HE":"HELSINKI"}
results=[]
for item in items:
 sym=item["symbol"]
 issues=[]
 f=a.stage/item["file"]
 if not f.is_file() or f.is_symlink() or hashlib.sha256(f.read_bytes()).hexdigest()!=item["sha256"]:issues.append("STAGE_SHA_MISMATCH")
 lines=f.read_text().splitlines() if f.is_file() else []
 if len(lines)!=item["rows"]:issues.append("ROW_COUNT_MISMATCH")
 prev=""
 for line in lines:
  try:
   row=json.loads(line)
   if row.get("symbol")!=sym or row.get("date","")<=prev or row.get("quality_status")!="legacy_unverified" or row.get("point_in_time_verified") is not False:issues.append("ROW_CONTRACT_INVALID");break
   prev=row["date"]
  except (ValueError,TypeError):issues.append("INVALID_JSON");break
 suffix=next((s for s in suffixes if sym.endswith(s)),None)
 if not suffix:issues.append("EXCHANGE_UNRESOLVED")
 # Yahoo metadata may report GBp, GBX, GBP, etc.; must verify unit rather than infer from .L.
 issues.extend(["CURRENCY_NOT_VERIFIED","MIC_NOT_VERIFIED","IDENTITY_NOT_VERIFIED"])
 results.append({"symbol":sym,"marketHint":suffixes.get(suffix),"bars":item["rows"],"issues":sorted(set(issues)),"eligibleForImport":False})
counts=collections.Counter(i for r in results for i in r["issues"])
report={"source":str(a.stage.resolve()),"total":len(results),"bars":sum(x["bars"] for x in results),
        "importAllowed":False,"blockers":dict(counts),"instruments":results,
        "note":"No instrument creation without verified exchange MIC, currency units, and identity."}
out=a.output or (a.stage/"preflight.json")
if out.exists():sys.exit("Refusing to overwrite preflight")
out.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({"report":str(out),"total":report["total"],"bars":report["bars"],"importAllowed":False,"blockers":dict(counts)},indent=2))
