#!/usr/bin/env bash
# MarketDataHub local-only launcher, independent from TrotValeur port 8000.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${MKD_PORT:-8100}"
[[ "$PORT" == 8100 ]] || { echo "Only dedicated MKD port 8100 supported"; exit 2; }
[[ -x .venv/bin/uvicorn ]] || { echo "Missing .venv/bin/uvicorn"; exit 2; }
export DATABASE_URL="${MKD_DATABASE_URL:-postgresql+psycopg://benoit@/market_data_hub?host=/var/run/postgresql&port=5433}"
.venv/bin/python - <<'PY'
import os
from sqlalchemy import create_engine,text
engine=create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    name=conn.execute(text('SELECT current_database()')).scalar()
    assert name=='market_data_hub', f'Unexpected database: {name}'
print('MKD database verified')
PY
if curl --silent --fail --max-time 3 "http://127.0.0.1:$PORT/health/live" >/dev/null; then
 echo "MKD already running on $PORT"
 exit 0
fi
if ss -ltn | grep -Eq "127\\.0\\.0\\.1:$PORT[[:space:]]"; then
 echo "Port $PORT already in use by a different service"; exit 3
fi
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$PORT" > /tmp/mkd-api-8100.log 2>&1 < /dev/null &
for _ in {1..20}; do
 if curl --silent --fail --max-time 2 "http://127.0.0.1:$PORT/health/live" >/dev/null; then
  echo "MKD ready on 127.0.0.1:$PORT"
  exit 0
 fi
 sleep 1
done
echo "MKD did not become healthy"; tail -30 /tmp/mkd-api-8100.log; exit 4
