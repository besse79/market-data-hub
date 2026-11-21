#!/usr/bin/env bash
# One-command MKD P0 integrated staging pilot. Read-only DB, bounded Yahoo downloads.
set -euo pipefail
ROOT='https://raw.githubusercontent.com/besse79/market-data-hub/prep/recette-wsl-20261121'
PY="$HOME/market-data-hub/.venv/bin/python"
[[ -x "$PY" ]] || { echo 'FAIL: MKD virtualenv missing'; exit 2; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/src" "$TMP/tests"
touch "$TMP/src/__init__.py"
for f in src/daily_stage.py src/yahoo_capture.py src/bulk_stage.py tests/test_daily_stage.py tests/test_yahoo_capture.py tests/test_bulk_stage.py scripts/trading-factory-export-yahoo-manifest.py; do
  mkdir -p "$TMP/$(dirname "$f")"
  curl -fsSL --max-time 30 "$ROOT/$f" -o "$TMP/$f"
done
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BASE="$HOME/trading-factory-reports/mkd-integrated"
mkdir -p "$BASE"
REPORT="$BASE/run-$STAMP.log"
exec > >(tee "$REPORT") 2>&1
echo "=== MKD integrated pilot $STAMP ==="
echo "REPORT=$REPORT"
echo '=== 1/4: Tests (isolated source) ==='
(cd "$TMP" && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TMP" "$PY" -m pytest -q -p no:cacheprovider tests)
echo '=== 2/4: Export DB Yahoo identifiers (read-only) ==='
MANIFEST_DIR="$BASE/manifests/$STAMP"
"$PY" "$TMP/scripts/trading-factory-export-yahoo-manifest.py" --output-dir "$MANIFEST_DIR"
echo '=== 3/4: Missing identifier coverage (read-only) ==='
"$PY" - <<'PY'
import psycopg
with psycopg.connect('host=/var/run/postgresql port=5433 dbname=market_data_hub user=benoit', options='-c default_transaction_read_only=on') as con:
 with con.cursor() as cur:
  cur.execute("""SELECT count(*) FROM public.instruments i WHERE NOT EXISTS
     (SELECT 1 FROM public.instrument_identifiers ii WHERE ii.instrument_id=i.id
      AND lower(ii.provider)='yahoo' AND ii.valid_to IS NULL)""")
  print('instruments_without_active_yahoo_identifier=',cur.fetchone()[0])
  cur.execute("""SELECT count(*) FROM public.eod_bars WHERE quality_status='legacy_unverified'""")
  print('legacy_bars_protected=',cur.fetchone()[0])
PY
echo '=== 4/4: Bounded resumable Yahoo capture ==='
# Fixed window: deterministic filenames for safe restart. No DB writes.
LIMIT="${MKD_BATCH_LIMIT:-25}"
[[ "$LIMIT" =~ ^[0-9]+$ ]] && ((LIMIT>=1 && LIMIT<=264)) || { echo 'FAIL: MKD_BATCH_LIMIT must be 1..264'; exit 2; }
OUT="$BASE/staging/2026-11-17_2026-11-21"
mkdir -p "$OUT"
(cd "$TMP" && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TMP" "$PY" - "$MANIFEST_DIR/yahoo-manifest.csv" "$OUT" "$LIMIT" <<'PY'
import json,sys
from src.bulk_stage import run
r=run(sys.argv[1],sys.argv[2],'2026-11-17','2026-11-21',max_symbols=int(sys.argv[3]),delay=2)
print(json.dumps(r,indent=2,ensure_ascii=False))
if r['failed']: sys.exit(3)
PY
)
echo '=== GO/NO-GO ==='
echo 'PASS: research-only staged collection; PIT=false PAPER=false'
echo 'No DB writes, Git modifications, migrations, scheduler starts or PAPER orders.'
echo "REPORT=$REPORT"
