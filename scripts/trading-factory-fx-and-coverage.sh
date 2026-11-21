#!/usr/bin/env bash
set -euo pipefail
PY="$HOME/market-data-hub/.venv/bin/python"
[[ -x "$PY" ]] || { echo 'FAIL: Python venv missing'; exit 2; }
ROOT='https://raw.githubusercontent.com/besse79/market-data-hub/prep/recette-wsl-20261121'
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
curl -fsSL --max-time 30 "$ROOT/scripts/trading-factory-fx-and-coverage.py" -o "$TMP/run.py"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$HOME/trading-factory-reports/mkd-fx/$STAMP"
mkdir -p "$OUT"
"$PY" "$TMP/run.py" --out "$OUT"
echo "REPORT_DIR=$OUT"
