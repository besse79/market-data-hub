#!/usr/bin/env bash
set -euo pipefail
ROOT='https://raw.githubusercontent.com/besse79/market-data-hub/prep/recette-wsl-20261121/scripts'
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fsSL --max-time 30 "$ROOT/trading-factory-full-264.sh" -o "$TMP/collect.sh"
curl -fsSL --max-time 30 "$ROOT/trading-factory-research-db-stage.sh" -o "$TMP/stage.sh"
echo '=== PHASE 1: complete/resume all 264 Yahoo mapped instruments ==='
bash "$TMP/collect.sh"
echo '=== PHASE 2: verified backup and isolated transactional PostgreSQL staging ==='
bash "$TMP/stage.sh"
echo '=== INTEGRATED COMPLETE: no PIT/PAPER eligibility, legacy history preserved ==='
