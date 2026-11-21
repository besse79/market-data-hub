#!/usr/bin/env bash
set -Eeuo pipefail
echo '=== MKD guarded runtime recovery ==='
cd "$HOME/market-data-hub"
test -x .venv/bin/python || { echo 'BLOCKED: missing MKD Python environment'; exit 2; }
echo '=== Local PostgreSQL 5433 identity ==='
if ! command -v psql >/dev/null; then echo 'BLOCKED: psql unavailable'; exit 2; fi
if ! pg_isready -h 127.0.0.1 -p 5433 >/dev/null; then echo 'BLOCKED: postgres 5433 not ready'; exit 2; fi
echo '=== PostgreSQL MKD credentials and schema probe (read only) ==='
if ! PGPASSWORD=mkd psql -X -h 127.0.0.1 -p 5433 -U mkd -d mkd -At -v ON_ERROR_STOP=1 -c "BEGIN READ ONLY; SELECT current_database(), current_user, (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('instruments','bars','identifiers')); ROLLBACK;" ; then
  echo 'BLOCKED: database identity/credentials not verified; no MKD service started'; exit 3
fi
if ! PGPASSWORD=mkd psql -X -h 127.0.0.1 -p 5433 -U mkd -d mkd -At -v ON_ERROR_STOP=1 -c "SELECT CASE WHEN to_regclass('public.instruments') IS NOT NULL AND to_regclass('public.bars') IS NOT NULL THEN 'MKD_SCHEMA_OK' ELSE 'MKD_SCHEMA_MISSING' END" | grep -qx MKD_SCHEMA_OK; then
 echo 'BLOCKED: expected MKD schema missing'; exit 3
fi
echo '=== Starting MKD API in separate process (no DB mutations) ==='
if ss -lnt | grep -Eq '127\\.0\\.0\\.1:8100\\b'; then
 echo 'Port 8100 already occupied; checking existing API'
else
 mkdir -p "$HOME/trading-factory-reports"
 LOG="$HOME/trading-factory-reports/mkd-api-$(date -u +%Y%m%dT%H%M%SZ).log"
 nohup env DATABASE_URL='postgresql+psycopg://mkd:mkd@127.0.0.1:5433/mkd' .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8100 > "$LOG" 2>&1 < /dev/null &
 echo "MKD process PID=$! log=$LOG"
fi
sleep 3
echo '=== MKD API health ==='
curl -fsS --connect-timeout 3 --max-time 10 http://127.0.0.1:8100/health/live || { echo 'BLOCKED: MKD API not healthy'; exit 4; }
echo
echo '=== W shadow comparison ==='
curl -sS -o /tmp/trading-factory-shadow-check.json --connect-timeout 3 --max-time 15 -w 'HTTP %{http_code}\n' 'http://127.0.0.1:3010/api/mkd-shadow?symbol=SAMPO.HE&analysis=true' || true
python3 - <<'PY'
import json
try:
 with open('/tmp/trading-factory-shadow-check.json') as f: d=json.load(f)
 for k in ('mode','source','paperEligible','backtestEligible','executionAuthorized','error','detail'):
  if k in d: print(k,':',d[k])
except Exception as e: print('Shadow JSON unavailable:',e)
PY
echo '=== Completed: no migration, no import, no scheduler, no git changes ==='
