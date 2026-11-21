#!/usr/bin/env bash
set -euo pipefail
ROOT='https://raw.githubusercontent.com/besse79/market-data-hub/prep/recette-wsl-20261121'
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/src" "$TMP/tests"
touch "$TMP/src/__init__.py"
for f in src/daily_stage.py src/yahoo_capture.py src/bulk_stage.py tests/test_daily_stage.py tests/test_yahoo_capture.py tests/test_bulk_stage.py; do
 curl -fsSL --max-time 30 "$ROOT/$f" -o "$TMP/$f"
done
PY="$HOME/market-data-hub/.venv/bin/python"
[[ -x "$PY" ]] || { echo 'FAIL: MKD Python venv unavailable'; exit 2; }
cd "$TMP"
echo '=== P0 isolated batch tests ==='
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TMP" "$PY" -m pytest -q -p no:cacheprovider tests
echo '=== Live 2-symbol bounded research batch ==='
printf 'symbol,currency\nSAMPO.HE,EUR\nAAPL,USD\n' > "$TMP/manifest.csv"
mkdir -p "$HOME/trading-factory-reports/yahoo-bulk"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TMP" timeout 150 "$PY" - "$TMP/manifest.csv" "$HOME/trading-factory-reports/yahoo-bulk" <<'PY'
import json,sys
from src.bulk_stage import run
r=run(sys.argv[1],sys.argv[2],"2026-11-17","2026-11-21",max_symbols=2,delay=2)
print(json.dumps(r,indent=2))
if r["failed"]: sys.exit(3)
PY
echo 'No PostgreSQL writes, migrations, Git modifications, scheduler starts or PAPER orders.'
