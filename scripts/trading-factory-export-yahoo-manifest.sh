#!/usr/bin/env bash
set -euo pipefail
ROOT='https://raw.githubusercontent.com/besse79/market-data-hub/prep/recette-wsl-20261121'
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fsSL --max-time 30 "$ROOT/scripts/trading-factory-export-yahoo-manifest.py" -o "$TMP/export.py"
PY="$HOME/market-data-hub/.venv/bin/python"
[[ -x "$PY" ]] || { echo 'FAIL: MKD venv absent'; exit 2; }
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$HOME/trading-factory-reports/mkd-manifests/$STAMP"
echo '=== Export Yahoo symbols from MKD (read-only) ==='
"$PY" "$TMP/export.py" --output-dir "$OUT"
echo "MANIFEST=$OUT/yahoo-manifest.csv"
echo '=== Manifest preview ==='
head -n 6 "$OUT/yahoo-manifest.csv"
echo 'No market-data downloads, PostgreSQL writes, Git changes, migrations or PAPER orders.'
