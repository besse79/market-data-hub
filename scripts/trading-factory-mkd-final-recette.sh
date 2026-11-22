#!/usr/bin/env bash
# MKD P0 closure gate: verify research FX staging and real isolated restore.
# Does not modify market_data_hub, its historical tables, Git or schedulers.
set -Eeuo pipefail
export LC_ALL=C
fail(){ echo "BLOCKED: $*" >&2; exit 1; }
[[ $(id -u) -ne 0 && -t 0 ]] || fail 'Interactive non-root WSL required'
for cmd in sudo pg_restore pg_dump pg_lsclusters sha256sum psql python3; do command -v "$cmd" >/dev/null || fail "Missing $cmd"; done
PY="$HOME/market-data-hub/.venv/bin/python"
[[ -x "$PY" ]] || fail 'MKD Python venv missing'
ROOT="$HOME/trading-factory-reports"
OUT="$ROOT/mkd-final-recette/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT";chmod 700 "$OUT"
exec > >(tee "$OUT/recette.log") 2>&1
echo "REPORT=$OUT/recette.log"
echo '=== 1/4: PostgreSQL identity and research staging ==='
"$PY" - "$OUT" <<'PY'
import json,sys
from pathlib import Path
import psycopg
out=Path(sys.argv[1])
with psycopg.connect('host=/var/run/postgresql port=5433 dbname=market_data_hub user=benoit',
                     options='-c default_transaction_read_only=on') as con:
 with con.cursor() as cur:
  cur.execute('SELECT current_database(),current_user,current_setting(\'port\')')
  identity=cur.fetchone()
  if identity!=('market_data_hub','benoit','5433'):raise RuntimeError('DB identity mismatch')
  cur.execute('SELECT count(*) FROM public.eod_bars'); bars=cur.fetchone()[0]
  cur.execute('SELECT count(*) FROM public.fx_eod'); fx=cur.fetchone()[0]
  cur.execute('SELECT count(*) FROM public.instruments'); instruments=cur.fetchone()[0]
  cur.execute("""SELECT count(DISTINCT instrument_id) FROM public.instrument_identifiers
    WHERE lower(provider)='yahoo' AND valid_to IS NULL"""); mapped=cur.fetchone()[0]
  cur.execute("SELECT to_regclass('mkd_research.yahoo_staging')::text,to_regclass('mkd_research.fx_staging')::text")
  staging=cur.fetchone()
  counts={}
  for key,table in [('yahoo','yahoo_staging'),('fx','fx_staging')]:
   if staging[0 if key=='yahoo' else 1] is None:counts[key]=None;continue
   cur.execute('SELECT count(*),count(*) FILTER (WHERE pit_eligible OR paper_eligible) FROM mkd_research.'+table)
   counts[key]=cur.fetchone()
  cur.execute("SELECT count(*) FROM public.eod_bars WHERE quality_status='valid'")
  certified=cur.fetchone()[0]
  cur.execute("SELECT count(*) FROM public.legacy_symbol_map WHERE NOT mic_verified")
  unverified_mic=cur.fetchone()[0]
result={'db':identity,'instruments':instruments,'mapped_yahoo':mapped,
        'unmapped':instruments-mapped,'legacy_eod_bars':bars,'fx_eod':fx,
        'staging_counts':counts,'certified_eod_bars':certified,
        'unverified_mic':unverified_mic,'pit_eligible':False,'paper_eligible':False}
(out/'inventory.json').write_text(json.dumps(result,indent=2,default=str)+'\n')
print(json.dumps(result,indent=2,default=str))
if counts['yahoo'] is None or counts['yahoo'][0]<1053 or counts['yahoo'][1]!=0:
 raise RuntimeError('Yahoo research staging missing or unsafe')
if counts['fx'] is None or counts['fx'][0]<24 or counts['fx'][1]!=0:
 raise RuntimeError('FX research staging missing or unsafe: run FX DB import first')
PY
echo '=== 2/4: Fresh full backup with integrity verification ==='
DUMP="$OUT/market_data_hub.dump"
pg_dump -h /var/run/postgresql -p 5433 -U benoit -d market_data_hub -Fc -f "$DUMP" || fail 'Backup failed'
[[ -s "$DUMP" ]] || fail 'Empty backup'
sha256sum "$DUMP" > "$DUMP.sha256"
sha256sum -c "$DUMP.sha256" || fail 'Backup hash mismatch'
pg_restore -l "$DUMP" > "$DUMP.toc" || fail 'Invalid dump catalog'
grep -q 'TABLE DATA.*eod_bars' "$DUMP.toc" || fail 'Missing EOD backup'
echo '=== 3/4: Restore into unique scratch database on port 5433 ==='
sudo -v || fail 'sudo unavailable'
scratch="mkd_restore_$(date -u +%Y%m%d%H%M%S)_$$"
[[ "$scratch" =~ ^mkd_restore_[0-9]{14}_[0-9]+$ ]] || fail 'Unsafe scratch DB name'
created=0
cleanup(){
 if [[ "$created" == 1 ]];then
  sudo -n -u postgres dropdb -h /var/run/postgresql -p 5433 -U postgres --if-exists "$scratch" || echo "WARNING scratch cleanup required: $scratch" >&2
 fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
existing=$(sudo -n -u postgres psql -XAt -h /var/run/postgresql -p 5433 -U postgres -d postgres -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM pg_database WHERE datname='$scratch'")
[[ "$existing" == 0 ]] || fail 'Scratch DB already exists'
sudo -n -u postgres createdb -h /var/run/postgresql -p 5433 -U postgres "$scratch" || fail 'Cannot create scratch DB'
created=1
sudo -n -u postgres pg_restore --exit-on-error --single-transaction --no-owner --no-acl -h /var/run/postgresql -p 5433 -U postgres -d "$scratch" < "$DUMP" || fail 'Restore failed'
echo '=== 4/4: Exact source/restore row counts, including research tables ==='
for table in public.instruments public.eod_bars public.fx_eod public.instrument_identifiers public.legacy_symbol_map mkd_research.yahoo_staging mkd_research.fx_staging;do
 q="SELECT count(*) FROM $table"
 source=$(sudo -n -u postgres psql -XAt -h /var/run/postgresql -p 5433 -U postgres -d market_data_hub -v ON_ERROR_STOP=1 -c "$q")
 restored=$(sudo -n -u postgres psql -XAt -h /var/run/postgresql -p 5433 -U postgres -d "$scratch" -v ON_ERROR_STOP=1 -c "$q")
 [[ "$source" == "$restored" ]] || fail "Mismatch $table source=$source restored=$restored"
 echo "PASS $table: $source"
done
echo 'PASS: verified full backup, real isolated restore and seven table counts'
echo 'NOTE: source counts are read after backup; concurrent writes can invalidate comparison.'
echo 'NO_GO: PIT/PAPER until provenance, FX historical coverage, mappings and app parity certified'
echo "BACKUP=$DUMP"
echo "REPORT=$OUT/recette.log"
