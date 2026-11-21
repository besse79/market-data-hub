#!/usr/bin/env bash
set -uo pipefail
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$HOME/trading-factory-reports/mkd-p0-$STAMP.json"
mkdir -p "$HOME/trading-factory-reports"
echo '=== MKD P0 read-only data audit ==='
cd "$HOME/market-data-hub" || exit 2
if [[ ! -x .venv/bin/python ]]; then echo 'FAIL: MKD .venv missing'; exit 2; fi
if ! curl -fsS --max-time 5 http://127.0.0.1:8100/health/live >/dev/null; then echo 'WARN: MKD API not responding; database audit continues'; fi
if ! curl -fsSL --max-time 20 'https://raw.githubusercontent.com/besse79/market-data-hub/prep/recette-wsl-20261121/scripts/trading-factory-mkd-p0-audit.py' | .venv/bin/python /dev/stdin --output "$OUT"; then
 echo 'FAIL: P0 audit failed'; exit 3
fi
echo "REPORT=$OUT"
echo '=== QuantEdge / BuffettValue isolated pytest ==='
FAIL=0
for repo in QuantEdge BuffettValue; do
  DIR="$HOME/$repo"
  VENV="$HOME/.cache/trading-factory-venvs/$repo"
  echo "--- $repo ---"
  if [[ ! -d "$DIR/tests" ]]; then echo "WARN: no tests directory for $repo"; continue; fi
  if [[ ! -x "$VENV/bin/python" ]]; then
    mkdir -p "$(dirname "$VENV")"
    python3 -m venv "$VENV" || { echo "FAIL: cannot create isolated venv for $repo"; FAIL=1; continue; }
  fi
  if ! "$VENV/bin/python" -c 'import pytest' >/dev/null 2>&1; then
    "$VENV/bin/python" -m pip install --disable-pip-version-check 'pytest>=8,<10' || { echo "WARN: pytest installation unavailable for $repo"; continue; }
  fi
  (cd "$DIR" && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$DIR" timeout 90 "$VENV/bin/python" -m pytest -q -p no:cacheprovider) || FAIL=1
done
echo '=== END: no database writes, migrations, imports, scheduler starts or Git changes ==='
exit "$FAIL"
