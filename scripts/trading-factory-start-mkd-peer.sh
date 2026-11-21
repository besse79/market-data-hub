#!/usr/bin/env bash
set -Eeuo pipefail
cd "$HOME/market-data-hub"
echo '=== MKD local peer authentication preflight ==='
test -x .venv/bin/python || { echo 'BLOCKED: .venv missing'; exit 2; }
command -v psql >/dev/null || { echo 'BLOCKED: psql missing'; exit 2; }
if ! psql -X -h /var/run/postgresql -p 5433 -U benoit -d market_data_hub -At -v ON_ERROR_STOP=1 -c "BEGIN READ ONLY; SELECT CASE WHEN current_database()='market_data_hub' AND to_regclass('public.eod_bars') IS NOT NULL AND to_regclass('public.instrument_identifiers') IS NOT NULL AND to_regclass('public.legacy_symbol_map') IS NOT NULL THEN 'MKD_OK' ELSE 'MKD_INVALID' END; ROLLBACK;" | grep -qx MKD_OK; then
 echo 'BLOCKED: local peer authentication or MKD schema verification failed'; exit 3
fi
echo 'MKD database and local peer authentication verified'
if curl -fsS --max-time 3 http://127.0.0.1:8100/health/live >/dev/null 2>&1; then
 echo 'MKD already responding on 8100'
else
 if ss -lnt | grep -Eq ':8100[[:space:]]'; then echo 'BLOCKED: port 8100 occupied'; exit 4; fi
 mkdir -p "$HOME/trading-factory-reports"
 LOG="$HOME/trading-factory-reports/mkd-api-$(date -u +%Y%m%dT%H%M%SZ).log"
 echo "Starting MKD API read-only, log=$LOG"
 nohup env DATABASE_URL='postgresql+psycopg://benoit@/market_data_hub?host=/var/run/postgresql&port=5433' PGOPTIONS='-c default_transaction_read_only=on' .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8100 > "$LOG" 2>&1 < /dev/null &
 for n in $(seq 1 20); do
  if curl -fsS --max-time 2 http://127.0.0.1:8100/health/live >/dev/null 2>&1; then break; fi
  sleep 1
 done
fi
echo '=== MKD health ==='
curl -fsS --max-time 5 http://127.0.0.1:8100/health/live; echo
echo '=== MKD legacy resolve SAMPO ==='
curl -sS --max-time 10 -o /tmp/tf-mkd-resolve.json -w 'HTTP %{http_code}\n' 'http://127.0.0.1:8100/v1/legacy/resolve?symbol=SAMPO.HE'
python3 - <<'PY'
import json
try:
 with open('/tmp/tf-mkd-resolve.json') as f: d=json.load(f)
 print({k:v for k,v in d.items() if k in ('symbol','currency','mic_verified','detail')})
except Exception as e: print('Non-JSON response:',e)
PY
echo '=== Weinstein shadow ==='
curl -sS --max-time 20 -o /tmp/tf-w-shadow.json -w 'HTTP %{http_code}\n' 'http://127.0.0.1:3010/api/mkd-shadow?symbol=SAMPO.HE&analysis=true'
python3 - <<'PY'
import json
try:
 with open('/tmp/tf-w-shadow.json') as f: d=json.load(f)
 print({k:v for k,v in d.items() if k in ('mode','source','paperEligible','backtestEligible','executionAuthorized','error','detail')})
except Exception as e: print('Non-JSON response:',e)
PY
echo 'No Git changes, database writes, imports, migrations, or scheduler starts.'
