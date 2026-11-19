#!/usr/bin/env python3
"""Safely import qualified non-PIT Yahoo data into MKD PostgreSQL.
Requires verified pg_dump backup and explicit --apply. All writes in one transaction.
"""
import argparse,datetime as dt,hashlib,json,os,subprocess,sys,uuid
from pathlib import Path
from decimal import Decimal
import psycopg
p=argparse.ArgumentParser()
p.add_argument("stage",type=Path)
p.add_argument("qualification",type=Path)
p.add_argument("--backup-dir",type=Path,required=True)
p.add_argument("--apply",action="store_true")
a=p.parse_args()
manifest_bytes=(a.stage/"manifest.json").read_bytes()
manifest=json.loads(manifest_bytes)
q=json.loads(a.qualification.read_text())
if hashlib.sha256(manifest_bytes).hexdigest()!=q.get("stageManifestSha256") or str(a.stage.resolve())!=q.get("stage"):sys.exit("Qualification mismatch")
staged={x["symbol"]:x for x in manifest["instruments"]}
qualified=[x for x in q["instruments"] if x["status"]=="QUALIFIED"]
if len(staged)!=266 or not qualified:sys.exit("No eligible instruments")
if len(set(x["symbol"] for x in qualified))!=len(qualified):sys.exit("Duplicate qualification")
conninfo="dbname=market_data_hub user=benoit host=/var/run/postgresql port=5433"
# Never silently use a different database.
with psycopg.connect(conninfo) as db:
 with db.cursor() as cur:
  cur.execute("SELECT current_database(),current_user")
  assert cur.fetchone()==("market_data_hub","benoit")
  cur.execute("SELECT symbol FROM legacy_symbol_map")
  known={r[0] for r in cur.fetchall()}
  cur.execute("SELECT symbol FROM instrument_identifiers WHERE provider='yahoo'")
  known.update(r[0] for r in cur.fetchall())
  overlaps=sorted(known.intersection(x["symbol"] for x in qualified))
  if overlaps:sys.exit("Existing symbols; refuse insert: "+str(overlaps[:10]))
db.rollback() if False else None
# Verify ALL source bytes and OHLCV before any database write.
rows_by_symbol={}
for x in qualified:
 item=staged[x["symbol"]]
 f=a.stage/item["file"]
 if not f.is_file() or f.is_symlink() or hashlib.sha256(f.read_bytes()).hexdigest()!=item["sha256"]:sys.exit("Bad staged SHA "+x["symbol"])
 rows=[];last=""
 for line in f.open():
  r=json.loads(line);date=r["date"]
  if r["symbol"]!=x["symbol"] or date<=last or r.get("quality_status")!="legacy_unverified" or r.get("point_in_time_verified") is not False:sys.exit("Bad provenance/order")
  last=date
  o,h,l,c=(Decimal(str(r[k])) for k in ("open","high","low","close"))
  v=int(r["volume"])
  if min(o,h,l,c)<=0 or h<max(o,c,l) or l>min(o,c,h) or v<0:sys.exit("Bad OHLCV")
  rows.append((dt.date.fromisoformat(date),o,h,l,c,v))
 if len(rows)!=item["rows"]:sys.exit("Row count mismatch")
 rows_by_symbol[x["symbol"]]=rows
print(json.dumps({"qualified":len(qualified),"blocked":266-len(qualified),"bars":sum(map(len,rows_by_symbol.values())),"apply":a.apply},indent=2))
if not a.apply:sys.exit(0)
a.backup_dir.mkdir(parents=True,exist_ok=False)
backup=a.backup_dir/"market_data_hub.dump"
with backup.open("wb") as out:
 subprocess.run(["pg_dump","-h","/var/run/postgresql","-p","5433","-U","benoit","-d","market_data_hub","-Fc"],stdout=out,check=True)
subprocess.run(["pg_restore","-l",str(backup)],stdout=subprocess.DEVNULL,check=True)
if backup.stat().st_size<1024:sys.exit("Backup unexpectedly small")
digest=hashlib.sha256(backup.read_bytes()).hexdigest()
(a.backup_dir/"backup.sha256").write_text(digest+"  market_data_hub.dump\n")
(a.backup_dir/"RESTORE.txt").write_text("STOP ALL MKD WRITERS FIRST. Restore only after explicit operator approval:\npg_restore -h /var/run/postgresql -p 5433 -U benoit -d market_data_hub --clean --if-exists --single-transaction market_data_hub.dump\n")
print("Verified backup:",backup,"sha256:",digest,flush=True)
inserted=0
with psycopg.connect(conninfo) as db:
 with db.transaction():
  with db.cursor() as cur:
   cur.execute("SELECT pg_advisory_xact_lock(77911019)")
   cur.execute("SELECT symbol FROM legacy_symbol_map")
   known={r[0] for r in cur.fetchall()}
   cur.execute("SELECT symbol FROM instrument_identifiers WHERE provider='yahoo'")
   known.update(r[0] for r in cur.fetchall())
   if known.intersection(rows_by_symbol):raise RuntimeError("Concurrent symbol conflict; rolled back")
   for x in qualified:
    symbol=x["symbol"];iid=uuid.uuid4();now=dt.datetime.now(dt.timezone.utc)
    cur.execute("INSERT INTO instruments (id,name,asset_type,status) VALUES (%s,%s,'equity','active')",(iid,x["name"]))
    cur.execute("INSERT INTO instrument_identifiers (instrument_id,provider,symbol,mic,currency,valid_from,valid_to) VALUES (%s,'yahoo',%s,%s,%s,%s,NULL)",(iid,symbol,x["mic"],x["currency"],now))
    cur.execute("INSERT INTO legacy_symbol_map (symbol,name,currency,instrument_id,mic,mic_verified) VALUES (%s,%s,%s,%s,%s,FALSE)",(symbol,x["name"],x["currency"],iid,x["mic"]))
    batch=[(iid,d,"yahoo",1,x["currency"],o,h,l,c,v,now,"legacy_unverified") for d,o,h,l,c,v in rows_by_symbol[symbol]]
    cur.executemany("INSERT INTO eod_bars (instrument_id,session_date,provider,revision,currency,open,high,low,close,volume,published_at,ingested_at,first_available_at,quality_status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s,NULL,%s)",batch)
    inserted+=len(batch)
   cur.execute("SELECT count(*) FROM eod_bars WHERE quality_status='legacy_unverified' AND published_at IS NOT NULL")
   if cur.fetchone()[0]:raise RuntimeError("Provenance invariant broken; rollback")
print(json.dumps({"committedInstruments":len(qualified),"committedBars":inserted,"blockedInstruments":266-len(qualified),"backup":str(backup)},indent=2))
