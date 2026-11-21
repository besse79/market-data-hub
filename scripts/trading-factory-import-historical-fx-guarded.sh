#!/usr/bin/env bash
# Import five-year Yahoo FX research into isolated mkd_research.fx_staging.
# Never writes public.fx_eod or historical production bars.
set -Eeuo pipefail
export LC_ALL=C
fail(){ echo "BLOCKED: $*" >&2; exit 1; }
PY="$HOME/market-data-hub/.venv/bin/python"
[[ -x "$PY" ]] || fail 'MKD virtualenv missing'
for cmd in pg_dump pg_restore sha256sum curl psql;do command -v "$cmd" >/dev/null || fail "Missing $cmd";done
BASE="$HOME/trading-factory-reports/mkd-historical-fx"
SOURCE="$(find "$BASE" -mindepth 1 -maxdepth 1 -type d -name '20*' | sort | tail -1)"
[[ -n "$SOURCE" && -f "$SOURCE/summary.json" ]] || fail 'Historical FX research not found'
OUT="$HOME/trading-factory-reports/mkd-historical-fx-import/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT";chmod 700 "$OUT"
exec > >(tee "$OUT/recette.log") 2>&1
echo "SOURCE=$SOURCE"
"$PY" - "$SOURCE/summary.json" <<'PY'
import json,sys
s=json.load(open(sys.argv[1]))
assert not s['errors'] and len(s['fx_pairs'])==6
assert all(v['observations']>=1000 for v in s['fx_pairs'].values())
assert s['pit_verified'] is False and s['paper_eligible'] is False and s['production_writes'] is False
print('PASS historical research manifest')
PY
echo '=== Pre-write backup and integrity ==='
DUMP="$OUT/market_data_hub-before-fx-historical.dump"
pg_dump -h /var/run/postgresql -p 5433 -U benoit -d market_data_hub -Fc -f "$DUMP"
[[ -s "$DUMP" ]] || fail 'Empty backup'
sha256sum "$DUMP" > "$DUMP.sha256"
sha256sum -c "$DUMP.sha256" || fail 'Checksum failure'
pg_restore -l "$DUMP" > "$DUMP.toc"
grep -q 'TABLE DATA.*eod_bars' "$DUMP.toc" || fail 'Incomplete backup'
before="$(PGOPTIONS='-c default_transaction_read_only=on' psql -XAt -h /var/run/postgresql -p 5433 -U benoit -d market_data_hub -v ON_ERROR_STOP=1 -c 'SELECT (SELECT count(*) FROM public.eod_bars)::text || chr(44) || (SELECT count(*) FROM public.fx_eod)::text')"
echo '=== Validated transactional research import ==='
curl -fsSL --max-time 30 'https://raw.githubusercontent.com/besse79/market-data-hub/prep/recette-wsl-20261121/scripts/trading-factory-import-fx-staging.py' -o "$OUT/import.py"
"$PY" "$OUT/import.py" --directory "$SOURCE" --backup "$DUMP"
after="$(PGOPTIONS='-c default_transaction_read_only=on' psql -XAt -h /var/run/postgresql -p 5433 -U benoit -d market_data_hub -v ON_ERROR_STOP=1 -c 'SELECT (SELECT count(*) FROM public.eod_bars)::text || chr(44) || (SELECT count(*) FROM public.fx_eod)::text')"
[[ "$before" == "$after" ]] || fail "Production row counts changed: $before -> $after"
"$PY" - <<'PY'
import psycopg
with psycopg.connect('host=/var/run/postgresql port=5433 dbname=market_data_hub user=benoit',options='-c default_transaction_read_only=on') as c:
 with c.cursor() as cur:
  cur.execute("""SELECT pair,count(*),min(session_date),max(session_date),
       count(*) FILTER (WHERE pit_eligible OR paper_eligible)
       FROM mkd_research.fx_staging GROUP BY pair ORDER BY pair""")
  rows=cur.fetchall()
  assert len(rows)==6,rows
  for pair,n,first,last,eligible in rows:
   assert n>=1000 and eligible==0,(pair,n,eligible)
   print(f'PASS {pair}: {n} rows {first}..{last}; eligible=0')
print('PASS six historical FX pairs in isolated staging')
PY
echo "PASS production counts unchanged: $after"
echo "BACKUP=$DUMP"
echo "REPORT=$OUT/recette.log"
echo 'NO_GO PIT/PAPER: no historical availability certification'
