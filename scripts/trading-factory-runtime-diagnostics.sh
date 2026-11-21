#!/usr/bin/env bash
set -uo pipefail
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DIR="$HOME/trading-factory-reports/$STAMP"
mkdir -p "$DIR"; exec > >(tee "$DIR/runtime-diagnostics.log") 2>&1
echo "=== Runtime diagnostic (read-only) ==="
echo "UTC $STAMP"
docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' || true
echo "=== Weinstein scanner timing and status ==="
for endpoint in /api/scanner /api/paper-candidates /api/mkd-shadow?symbol=SAMPO.HE; do
  echo "endpoint=$endpoint"
  curl --noproxy '*' -sS -o "$DIR/response.json" --connect-timeout 3 --max-time 120 -w 'HTTP=%{http_code} time=%{time_total}s bytes=%{size_download}\n' "http://127.0.0.1:3010$endpoint" || echo "curl exit=$?"
  python3 - "$DIR/response.json" <<'PY'
import json,sys
try:
 with open(sys.argv[1]) as f: x=json.load(f)
 if isinstance(x,dict):
  print('keys:',sorted(x.keys()))
  for k in ('error','detail','message','status','mode'): 
   if k in x: print(k,str(x[k])[:500])
  for k in ('results','candidates'): 
   if isinstance(x.get(k),list): print(k,'count',len(x[k]))
except Exception as e: print('No JSON response:',type(e).__name__)
PY
done
echo "=== Web logs ==="
docker logs --tail 100 cto_weinstein-web-1 2>&1 || true
echo "=== MKD local process and sockets ==="
ss -lnt 2>/dev/null | grep -E ':(8100|3010|5433)\b' || true
ps -eo pid,etimes,comm,args | grep -E '[u]vicorn|[m]arket.data.hub|[m]kd' | head -25 || true
echo "=== MKD compose files (metadata only) ==="
find "$HOME/market-data-hub" -maxdepth 3 -type f \( -name 'docker-compose*.yml' -o -name 'compose*.yaml' -o -name '*start*.sh' \) -print 2>/dev/null | head -30
echo "Report: $DIR"
