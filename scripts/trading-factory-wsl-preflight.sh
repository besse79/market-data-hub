#!/usr/bin/env bash
# Trading Factory WSL preflight: read-only, safe to run from any directory.
set -uo pipefail
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ROOT="${HOME}/trading-factory-reports/${STAMP}"
mkdir -p "$ROOT"
exec > >(tee "$ROOT/preflight.log") 2>&1
echo "Trading Factory preflight UTC=$STAMP"
echo "Host: $(hostname) | user: $(id -un)"
if command -v uname >/dev/null; then uname -a; fi
if command -v docker >/dev/null; then
  echo "=== Docker status (read-only) ==="
  docker version --format '{{.Server.Version}}' 2>&1 || true
  docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>&1 || true
else echo "Docker unavailable"; fi
for pair in "market-data-hub:market-data-hub" "cto-weinstein-trader:cto-weinstein-trader" "QuantEdge:QuantEdge" "BuffettValue:BuffettValue"; do
  folder="${pair%%:*}"
  path="${HOME}/${folder}"
  echo "=== ${folder} ==="
  if [[ ! -d "$path/.git" ]]; then echo "NOT INSTALLED at $path"; continue; fi
  (
    cd "$path" || exit
    printf 'branch='; git branch --show-current
    printf 'commit='; git rev-parse HEAD
    printf 'status='; if [[ -z "$(git status --porcelain)" ]]; then echo CLEAN; else echo MODIFIED; fi
    git remote -v | sed -E 's#(https?://)[^/@]+@#\1***@#g' | head -2
    if [[ -f docker-compose.yml ]]; then
      echo "compose service definitions:"
      grep -E '^  [a-zA-Z0-9_-]+:$' docker-compose.yml || true
    fi
  )
done
echo "=== Local HTTP probes ==="
for port in 3000 8000 8503 8504 8010 8011; do
  if command -v curl >/dev/null; then
    code="$(curl --noproxy '*' -sS --connect-timeout 1 --max-time 3 -o /dev/null -w '%{http_code}' "http://127.0.0.1:${port}/" 2>/dev/null || true)"
    echo "127.0.0.1:${port} HTTP ${code:-unreachable}"
  fi
done
echo "=== Toolchain ==="
for bin in git python3 node npm docker; do
  if command -v "$bin" >/dev/null; then echo "$bin: $(command -v "$bin")"; else echo "$bin: absent"; fi
done
cat > "$ROOT/STATUS.txt" <<'EOF'
READ-ONLY PREFLIGHT COMPLETE.
No database writes, migrations, order placement, or service restarts were performed.
HTTP 404/405 may indicate a live API with no root endpoint.
NEXT: run tests only in isolated environments and approve backups before any import.
EOF
echo "Report: $ROOT"
