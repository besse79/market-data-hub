#!/usr/bin/env bash
set -euo pipefail
ROOT='https://raw.githubusercontent.com/besse79/market-data-hub/prep/recette-wsl-20261121'
PY="$HOME/market-data-hub/.venv/bin/python"
[[ -x "$PY" ]] || { echo 'FAIL Python venv missing'; exit 2; }
for cmd in pg_dump pg_restore psql sha256sum; do command -v "$cmd" >/dev/null || { echo "FAIL missing $cmd"; exit 2; }; done
BASE="$HOME/trading-factory-reports"
FX="$(find "$BASE/mkd-fx" -mindepth 1 -maxdepth 1 -type d -name '20*' | sort | tail -1)"
[[ -n "$FX" && -f "$FX/summary.json" ]] || { echo 'FAIL FX research artifacts absent'; exit 2; }
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BASE/mkd-p0/$STAMP";mkdir -p "$OUT"
exec > >(tee "$OUT/recette.log") 2>&1
echo "=== MKD P0 integrated FX stage + coverage ==="
echo "FX_SOURCE=$FX"
echo '=== Verify FX collection completed ==='
"$PY" - "$FX/summary.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert not d["errors"] and len(d["fx_pairs"])==6
assert all(v["observations"]>0 for v in d["fx_pairs"].values())
assert d["pit_verified"] is False and d["paper_eligible"] is False
print("PASS 6 FX pairs staged in JSON")
PY
echo '=== PostgreSQL backup before any write ==='
BACKUP="$OUT/market_data_hub-before-fx.dump"
pg_dump -h /var/run/postgresql -p 5433 -U benoit -d market_data_hub -Fc -f "$BACKUP"
[[ -s "$BACKUP" ]] || exit 3
pg_restore -l "$BACKUP" > "$BACKUP.toc"
grep -q 'TABLE DATA.*eod_bars' "$BACKUP.toc" || { echo 'FAIL missing eod_bars'; exit 3; }
sha256sum "$BACKUP" > "$BACKUP.sha256"
sha256sum -c "$BACKUP.sha256"
echo '=== Existing historical row counts ==='
BEFORE="$(PGOPTIONS='-c default_transaction_read_only=on' psql -XAt -h /var/run/postgresql -p 5433 -U benoit -d market_data_hub -c 'SELECT (SELECT count(*) FROM public.eod_bars)::text || chr(44) || (SELECT count(*) FROM public.fx_eod)::text')"
curl -fsSL --max-time 30 "$ROOT/scripts/trading-factory-import-fx-staging.py" -o "$OUT/import-fx.py"
echo '=== Transactional isolated FX import ==='
"$PY" "$OUT/import-fx.py" --directory "$FX" --backup "$BACKUP"
AFTER="$(PGOPTIONS='-c default_transaction_read_only=on' psql -XAt -h /var/run/postgresql -p 5433 -U benoit -d market_data_hub -c 'SELECT (SELECT count(*) FROM public.eod_bars)::text || chr(44) || (SELECT count(*) FROM public.fx_eod)::text')"
[[ "$BEFORE" == "$AFTER" ]] || { echo "FAIL legacy counts $BEFORE -> $AFTER"; exit 4; }
echo "PASS historical eod_bars,fx_eod counts unchanged: $AFTER"
echo '=== Missing Yahoo mappings: read-only candidate evidence ==='
"$PY" - "$OUT" <<'PY'
import csv,json,sys
from pathlib import Path
import psycopg
out=Path(sys.argv[1])
with psycopg.connect('host=/var/run/postgresql port=5433 dbname=market_data_hub user=benoit',options='-c default_transaction_read_only=on') as con:
 with con.cursor() as cur:
  cur.execute("""SELECT i.id::text,i.name,i.asset_type,i.status
    FROM public.instruments i WHERE NOT EXISTS
    (SELECT 1 FROM public.instrument_identifiers ii WHERE ii.instrument_id=i.id
     AND lower(ii.provider)='yahoo' AND ii.valid_to IS NULL)
    ORDER BY i.name,i.id""")
  missing=cur.fetchall()
  cur.execute("""SELECT column_name FROM information_schema.columns
    WHERE table_schema='public' AND table_name='legacy_symbol_map' ORDER BY ordinal_position""")
  legacy_columns=[r[0] for r in cur.fetchall()]
  cur.execute("SELECT count(*) FROM public.legacy_symbol_map")
  legacy_count=cur.fetchone()[0]
with (out/'unmapped-instruments.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['instrument_id','name','asset_type','status','mapping_state'])
 for r in missing:w.writerow([*r,'unmapped_yahoo'])
result={'unmapped_count':len(missing),'legacy_symbol_map_rows':legacy_count,
 'legacy_symbol_map_columns':legacy_columns,'auto_mapped':0,
 'requires_verified_provider_evidence':True}
(out/'coverage.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
PY
echo '=== Recovery information ==='
echo "BACKUP=$BACKUP"
echo 'Archive integrity and catalog verified. Actual restore into a separate DB remains to be tested.'
echo "REPORT=$OUT/recette.log"
echo 'PIT=false PAPER=false; no production historical data writes.'
