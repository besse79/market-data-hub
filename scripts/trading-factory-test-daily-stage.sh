#!/usr/bin/env bash
set -euo pipefail
ROOT='https://raw.githubusercontent.com/besse79/market-data-hub/prep/recette-wsl-20261121'
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/src" "$TMP/tests"
touch "$TMP/src/__init__.py"
curl -fsSL "$ROOT/src/daily_stage.py" -o "$TMP/src/daily_stage.py"
curl -fsSL "$ROOT/tests/test_daily_stage.py" -o "$TMP/tests/test_daily_stage.py"
cd "$TMP"
echo '=== MKD P0 daily stage fail-closed tests ==='
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TMP" "$HOME/market-data-hub/.venv/bin/python" -m pytest -q -p no:cacheprovider tests/test_daily_stage.py
echo 'No DB writes, Git changes, downloads of market data, or scheduler starts.'
