#!/usr/bin/env bash
set -uo pipefail
ROOT="$HOME/trading-factory-reports"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$ROOT"
REPORT="$ROOT/integrated-recette-$STAMP.txt"
exec > >(tee "$REPORT") 2>&1
pass=0; fail=0; warn=0
ok(){ echo "PASS $*"; pass=$((pass+1)); }
bad(){ echo "FAIL $*"; fail=$((fail+1)); }
note(){ echo "WARN $*"; warn=$((warn+1)); }
http(){ local label="$1" url="$2" expected="$3" seconds="$4" out code; out="$(mktemp)"; code="$(curl -sS --max-time "$seconds" -o "$out" -w '%{http_code}' "$url" 2>/dev/null)" || code=000; if [[ "$code" == "$expected" ]]; then ok "$label HTTP $code"; else bad "$label HTTP $code (expected $expected)"; fi; rm -f "$out"; }
echo "=== Trading Factory integrated read-only recette $STAMP ==="
echo '=== Runtime ==='
http 'MKD health' 'http://127.0.0.1:8100/health/live' 200 6
http 'MKD legacy resolve' 'http://127.0.0.1:8100/v1/legacy/resolve?symbol=SAMPO.HE' 200 10
http 'MKD PIT rejects future as_of' 'http://127.0.0.1:8100/v1/bars?instrument_id=00000000-0000-0000-0000-000000000000&start=2026-11-01&end=2026-11-02&as_of=2099-01-01T00%3A00%3A00%2B00%3A00&provider=yahoo' 422 10
http 'Weinstein scanner' 'http://127.0.0.1:3010/api/scanner' 200 90
http 'Weinstein PAPER candidates' 'http://127.0.0.1:3010/api/paper-candidates' 200 90
echo '=== Shadow policy ==='
SHADOW="$(mktemp)"
CODE="$(curl -sS --max-time 25 -o "$SHADOW" -w '%{http_code}' 'http://127.0.0.1:3010/api/mkd-shadow?symbol=SAMPO.HE&analysis=true' 2>/dev/null)" || CODE=000
if [[ "$CODE" == 200 ]] && python3 - "$SHADOW" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert d.get("mode")=="READ_ONLY_SHADOW",d
assert d.get("paperEligible") is False,d
assert d.get("backtestEligible") is False,d
assert d.get("executionAuthorized") is False,d
assert d.get("source")=="MKD_LEGACY_NON_PIT",d
PY
then ok 'W/MKD shadow fail-closed flags'; else bad "W/MKD shadow HTTP $CODE or policy mismatch"; fi
rm -f "$SHADOW"
echo '=== Database identity and quality (read-only) ==='
if psql -X -h /var/run/postgresql -p 5433 -U benoit -d market_data_hub -v ON_ERROR_STOP=1 -At <<'SQL'
BEGIN READ ONLY;
SELECT 'database='||current_database();
SELECT 'instruments='||count(*) FROM public.instruments;
SELECT 'bars='||count(*) FROM public.eod_bars;
SELECT 'quality='||coalesce(quality_status,'NULL')||':'||count(*) FROM public.eod_bars GROUP BY quality_status ORDER BY quality_status;
SELECT 'fx='||count(*) FROM public.fx_eod;
SELECT 'legacy_mappings='||count(*) FROM public.legacy_symbol_map;
ROLLBACK;
SQL
then ok 'MKD SQL read-only statistics'; else bad 'MKD SQL statistics'; fi
echo '=== Python test suites (no installs) ==='
for repo in QuantEdge BuffettValue; do
 path="$HOME/$repo"
 if [[ ! -d "$path" ]]; then note "$repo workspace absent"; continue; fi
 if [[ -x "$path/.venv/bin/python" ]]; then PY="$path/.venv/bin/python"; else PY=python3; fi
 if (cd "$path" && "$PY" -c 'import pytest' >/dev/null 2>&1); then
   if (cd "$path" && PYTHONDONTWRITEBYTECODE=1 timeout 90 "$PY" -m pytest -q -p no:cacheprovider); then ok "$repo tests"; else bad "$repo tests"; fi
 else
   note "$repo pytest unavailable (no dependency installation)"
 fi
done
echo '=== Scheduler ==='
if [[ "$(docker inspect -f '{{.State.Running}}' cto_weinstein-scheduler-1 2>/dev/null)" == true ]]; then bad 'W scheduler unexpectedly running'; else ok 'W scheduler stopped'; fi
echo "=== SUMMARY PASS=$pass FAIL=$fail WARN=$warn ==="
echo "REPORT=$REPORT"
echo 'No imports, migrations, Git changes, scheduler starts or database writes.'
[[ "$fail" -eq 0 ]]
