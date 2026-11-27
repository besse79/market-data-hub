#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://benoit@/market_data_hub?host=/var/run/postgresql&port=5433}"
export PYTHONPATH="$PWD"
mkdir -p "$HOME/market-data-hub/evidence"
exec 9>"$HOME/market-data-hub/evidence/daily-eod.lock"
flock -n 9 || { echo "Collection already running"; exit 1; }
end="$(TZ=Europe/Paris date +%F)"
start="$(TZ=Europe/Paris date -d '7 days ago' +%F)"
python_bin="${MKD_PYTHON:-$HOME/market-data-hub/.venv/bin/python}"
"$python_bin" -m app.collect_all --start "$start" --end "$end" --batch-size 50 --delay 3 --output "$HOME/market-data-hub/evidence/daily-$(date -u +%Y%m%dT%H%M%SZ).json"
