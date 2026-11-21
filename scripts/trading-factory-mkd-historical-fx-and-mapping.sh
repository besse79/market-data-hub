#!/usr/bin/env bash
# MKD P0 next gate: historical FX research capture and independent mapping evidence.
# No production table writes; PIT and PAPER remain disabled.
set -Eeuo pipefail
ROOT='https://raw.githubusercontent.com/besse79/market-data-hub/prep/recette-wsl-20261121'
PY="$HOME/market-data-hub/.venv/bin/python"
[[ -x "$PY" ]] || { echo 'BLOCKED: missing MKD venv' >&2; exit 2; }
OUT="$HOME/trading-factory-reports/mkd-historical-fx/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"; chmod 700 "$OUT"
curl -fsSL --max-time 30 "$ROOT/scripts/trading-factory-fx-historical.py" -o "$OUT/collect.py"
echo "REPORT=$OUT"
"$PY" "$OUT/collect.py" --output "$OUT" --start 2021-11-01 --end 2026-11-21
