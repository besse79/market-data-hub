#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT="$HOME/trading-factory-reports/$STAMP"
mkdir -p "$REPORT"
exec > >(tee "$REPORT/workspaces.log") 2>&1
echo "=== Trading Factory workspace preparation ==="
for spec in "QuantEdge:besse79/QuantEdge" "BuffettValue:besse79/BuffettValue"; do
  name="${spec%%:*}"; remote="${spec#*:}"; dir="$HOME/$name"
  if [[ -e "$dir" ]]; then
    if [[ -d "$dir/.git" ]]; then echo "PRESERVED existing repository: $dir"; else echo "BLOCKED non-Git directory: $dir"; exit 2; fi
  else
    echo "Cloning $remote into $dir"
    git clone "https://github.com/$remote.git" "$dir"
  fi
  git -C "$dir" status --short --branch
done
echo "=== Existing workspaces, no modifications ==="
for name in market-data-hub cto-weinstein-trader; do
  dir="$HOME/$name"
  if [[ -d "$dir/.git" ]]; then
    printf '%s branch=' "$name"; git -C "$dir" branch --show-current
    printf '%s changes=' "$name"; git -C "$dir" status --porcelain | wc -l
  else echo "$name MISSING"; fi
done
echo "=== Docker containers including stopped ==="
docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' || true
echo "=== Actual service endpoints ==="
for target in "3010:/api/scanner" "3010:/api/paper-candidates" "8100:/health/live" "8100:/health/ready" "3000:/" "8000:/"; do
  port="${target%%:*}"; route="${target#*:}"
  code="$(curl --noproxy '*' -s -o /dev/null --connect-timeout 2 --max-time 12 -w '%{http_code}' "http://127.0.0.1:$port$route" || true)"
  echo "http://127.0.0.1:$port$route HTTP ${code:-000}"
done
echo "DONE: no service starts, migrations, database writes or Git branch changes"
echo "Report: $REPORT"
