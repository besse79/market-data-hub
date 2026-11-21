#!/usr/bin/env bash
set -euo pipefail
ROOT='https://raw.githubusercontent.com/besse79/market-data-hub/prep/recette-wsl-20261121'
PY="$HOME/market-data-hub/.venv/bin/python"
[[ -x "$PY" ]] || { echo 'FAIL: MKD venv missing'; exit 2; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/src" "$TMP/tests"; touch "$TMP/src/__init__.py"
for f in src/fx_stage.py tests/test_fx_stage.py; do
 curl -fsSL --max-time 30 "$ROOT/$f" -o "$TMP/$f"
done
echo '=== MKD FX unit tests ==='
(cd "$TMP" && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TMP" "$PY" -m unittest discover -s tests -p 'test_fx_stage.py' -v)
echo '=== FX currency requirements from real mapped Yahoo instruments ==='
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT="$HOME/trading-factory-reports/mkd-integrated/fx-coverage-$STAMP.json"
(cd "$TMP" && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TMP" "$PY" - "$REPORT" <<'PY'
import json,sys
from collections import Counter
from pathlib import Path
import psycopg
from src.fx_stage import fx_requirement
with psycopg.connect('host=/var/run/postgresql port=5433 dbname=market_data_hub user=benoit',
                     options='-c default_transaction_read_only=on') as conn:
 with conn.cursor() as cur:
  cur.execute("""SELECT currency,count(*) FROM public.instrument_identifiers
                 WHERE lower(provider)='yahoo' AND valid_to IS NULL
                 GROUP BY currency ORDER BY currency""")
  currencies=dict(cur.fetchall())
  cur.execute("SELECT count(*) FROM public.fx_eod")
  stored_fx=cur.fetchone()[0]
pairs={}
unsupported={}
for currency,n in currencies.items():
 try: pairs[currency]={"count":n,**fx_requirement(currency)}
 except ValueError: unsupported[currency]=n
out={"yahoo_active_identifiers":sum(currencies.values()),
     "currency_requirements":pairs,"unsupported":unsupported,
     "existing_fx_eod_rows":stored_fx,
     "pit_verified":False,"paper_eligible":False}
Path(sys.argv[1]).write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps(out,indent=2))
if unsupported: sys.exit(3)
PY
)
echo "REPORT=$REPORT"
echo 'Read-only PostgreSQL, no live FX ingestion, no data certification, no scheduler starts.'
