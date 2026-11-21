#!/usr/bin/env bash
# Read-only MKD runtime preflight. Never prints credentials.
set -Eeuo pipefail
cd "${HOME}/market-data-hub"
echo '=== MKD runtime preflight (read-only) ==='
echo "Branch: $(git branch --show-current)"
echo '=== Database metadata (local PostgreSQL 5433) ==='
sudo -u postgres psql -p 5433 -d market_data_hub -X -v ON_ERROR_STOP=1 -Atc "
SELECT 'database=' || current_database();
SELECT 'bars=' || count(*) FROM public.eod_bars;
SELECT 'legacy_symbols=' || count(*) FROM public.legacy_symbol_map;
SELECT 'mkd_read_' || tablename || '=' ||
       has_table_privilege('mkd', 'public.' || tablename, 'SELECT')
FROM pg_tables WHERE schemaname='public' ORDER BY tablename;
"
echo '=== API local health ==='
curl -sS --max-time 5 -w '\nHTTP %{http_code}\n' http://127.0.0.1:8000/health/live || true
echo '=== Weinstein container network ==='
docker exec cto_weinstein-web-1 node -e 'fetch("http://host.docker.internal:8000/health/live").then(async r=>console.log("MKD HTTP",r.status,await r.text())).catch(e=>console.log("MKD network error:",e.message))'
echo '=== Weinstein MKD endpoint (no secrets) ==='
docker exec cto_weinstein-web-1 node -e 'console.log("MKD_BASE_URL="+(process.env.MKD_BASE_URL||"<unset>"));console.log("MKD_SHADOW_ENABLED="+(process.env.MKD_SHADOW_ENABLED||"<unset>"))'
echo '=== Backup candidates (metadata only) ==='
find "$HOME/market-data-hub/evidence" -maxdepth 3 -type f \( -name '*.dump' -o -name '*.backup' \) -printf '%TY-%Tm-%Td %TH:%TM %s %p\n' 2>/dev/null | sort -r | head -10 || true
echo '=== End: no modifications performed ==='
