#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
ROOT="$HOME/trading-factory-agent"
mkdir -p "$ROOT/reports"
REPORT="$ROOT/reports/runner-prerequisites.txt"
{
  echo "Trading Factory runner prerequisite check"
  date -u +%FT%TZ
  echo "--- binaries ---"
  for cmd in gh git curl tar python3 node npm docker codex; do
    if command -v "$cmd" >/dev/null 2>&1; then printf '%s: %s\n' "$cmd" "$(command -v "$cmd")"; else echo "$cmd: MISSING"; fi
  done
  echo "--- GitHub CLI auth ---"
  if gh auth status >/dev/null 2>&1; then echo "gh_auth: OK"; else echo "gh_auth: NOT_AUTHENTICATED"; fi
  echo "--- repo visibility ---"
  if gh repo view besse79/market-data-hub --json nameWithOwner -q .nameWithOwner 2>/dev/null; then :; else echo "repo: UNAVAILABLE"; fi
  echo "--- runner registration authorization (no token output) ---"
  status="$(gh api -X GET repos/besse79/market-data-hub/actions/runners --jq '.total_count' 2>/dev/null)" && echo "runner_api: ACCESSIBLE (registered runners: $status)" || echo "runner_api: ACCESS_DENIED_OR_UNAVAILABLE"
  echo "--- local runtime ---"
  if docker info >/dev/null 2>&1; then echo "docker: OK"; else echo "docker: UNAVAILABLE"; fi
  if command -v codex >/dev/null 2>&1; then codex --version 2>&1 | head -n 1; fi
  echo "--- WSL ---"
  uname -srm
  echo "No secrets printed. No runner installed. No DB writes."
} | tee "$REPORT"
echo "REPORT=$REPORT"
