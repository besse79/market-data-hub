#!/usr/bin/env bash
set -euo pipefail
ROOT='https://raw.githubusercontent.com/besse79/market-data-hub/prep/recette-wsl-20261121'
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/src" "$TMP/tests"
touch "$TMP/src/__init__.py"
for file in src/daily_stage.py src/yahoo_capture.py tests/test_daily_stage.py tests/test_yahoo_capture.py; do
 curl -fsSL --max-time 25 "$ROOT/$file" -o "$TMP/$file"
done
PY="$HOME/market-data-hub/.venv/bin/python"
[[ -x "$PY" ]] || { echo 'FAIL: MKD venv absent'; exit 2; }
cd "$TMP"
echo '=== MKD P0: staged collector unit tests ==='
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TMP" "$PY" -m pytest -q -p no:cacheprovider tests/
echo '=== Yahoo Finance single-symbol real network capture ==='
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$HOME/trading-factory-reports/yahoo-staging/SAMPO.HE-$STAMP.json"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TMP" timeout 75 "$PY" -m src.yahoo_capture --symbol SAMPO.HE --currency EUR --start 2026-11-17 --end 2026-11-21 --output "$OUT"
"$PY" - "$OUT" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert d['point_in_time_verified'] is False
assert d['paper_eligible'] is False
assert all(x['quality_status']=='staged_unverified' for x in d['observations'])
print('PASS: live Yahoo capture validated, no PIT or PAPER authorization')
print('ROWS:',len(d['observations']))
PY
echo "STAGING_REPORT=$OUT"
echo 'No PostgreSQL writes, migrations, Git changes, scheduler starts or PAPER orders.'
