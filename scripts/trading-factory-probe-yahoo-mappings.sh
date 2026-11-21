#!/usr/bin/env bash
# Read-only first batch of evidence-based Yahoo candidate probes.
set -Eeuo pipefail
PY="$HOME/market-data-hub/.venv/bin/python"
[[ -x "$PY" ]] || { echo 'BLOCKED missing MKD venv' >&2;exit 2; }
OUT="$HOME/trading-factory-reports/mkd-mapping-evidence/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT";chmod 700 "$OUT"
curl -fsSL --max-time 30 'https://raw.githubusercontent.com/besse79/market-data-hub/prep/recette-wsl-20261121/scripts/trading-factory-probe-yahoo-mappings.py' -o "$OUT/probe.py"
"$PY" "$OUT/probe.py" --output "$OUT" --limit 40 --pause 2
echo "REPORT=$OUT/summary.json"
echo "CANDIDATES=$OUT/mapping-candidates.csv"
