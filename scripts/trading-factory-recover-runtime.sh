#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT="$HOME/trading-factory-reports/$STAMP"
mkdir -p "$REPORT"
exec > >(tee "$REPORT/recovery.log") 2>&1
echo "=== Trading Factory runtime recovery (existing containers only) ==="
for name in cto_weinstein-db-1 cto_weinstein-web-1; do
  docker inspect "$name" >/dev/null || { echo "BLOCKED: container $name absent"; exit 2; }
  echo "$name state=$(docker inspect -f '{{.State.Status}}' "$name")"
done
echo "=== Volume mount verification ==="
for name in cto_weinstein-db-1 cto_weinstein-web-1; do
  docker inspect -f '{{range .Mounts}}{{println .Type .Source .Destination}}{{end}}' "$name"
done
echo "=== Starting existing Weinstein database container ==="
if [[ "$(docker inspect -f '{{.State.Running}}' cto_weinstein-db-1)" != true ]]; then
  if ! docker start cto_weinstein-db-1; then
    echo "BLOCKED: database failed to start; web not started"
    docker logs --tail 80 cto_weinstein-db-1 || true
    exit 3
  fi
fi
echo "=== Database health ==="
for i in $(seq 1 30); do
  health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' cto_weinstein-db-1)"
  [[ "$health" == healthy ]] && break
  [[ "$health" == unhealthy || "$health" == exited ]] && break
  sleep 2
done
echo "Database health: $health"
if [[ "$health" != healthy ]]; then
  docker logs --tail 80 cto_weinstein-db-1 || true
  echo "BLOCKED: DB not healthy; web not started"
  exit 4
fi
echo "=== Starting existing Weinstein web container ==="
if [[ "$(docker inspect -f '{{.State.Running}}' cto_weinstein-web-1)" != true ]]; then
  docker start cto_weinstein-web-1 || { docker logs --tail 80 cto_weinstein-web-1 || true; exit 5; }
fi
echo "=== HTTP checks ==="
for spec in "3010:/api/scanner" "3010:/api/paper-candidates" "8100:/health/live"; do
  port="${spec%%:*}"; route="${spec#*:}"; code=000
  for i in 1 2 3; do
    code="$(curl --noproxy '*' -s -o /dev/null --connect-timeout 2 --max-time 60 -w '%{http_code}' "http://127.0.0.1:$port$route" || true)"
    [[ "$code" != 000 ]] && break
    sleep 3
  done
  echo "http://127.0.0.1:$port$route HTTP $code"
done
echo "=== Runtime states ==="
docker ps -a --filter name=cto_weinstein --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo "No Git branch changes, compose recreation, migrations, imports or scheduler starts"
echo "Report: $REPORT"
