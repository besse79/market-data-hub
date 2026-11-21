#!/usr/bin/env bash
set -euo pipefail
ROOT='https://raw.githubusercontent.com/besse79/market-data-hub/prep/recette-wsl-20261121'
PY="$HOME/market-data-hub/.venv/bin/python"
[[ -x "$PY" ]] || { echo 'FAIL MKD venv missing'; exit 2; }
for command in pg_dump pg_restore psql sha256sum; do command -v "$command" >/dev/null || { echo "FAIL missing $command"; exit 2; }; done
BASE="$HOME/trading-factory-reports/mkd-integrated"
SOURCE="$BASE/staging/2026-11-17_2026-11-21"
[[ -d "$SOURCE" ]] || { echo 'FAIL: run full-264 collection first'; exit 2; }
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$HOME/trading-factory-reports/mkd-backups"
mkdir -p "$BACKUP_DIR"
BACKUP="$BACKUP_DIR/market_data_hub-before-research-staging-$STAMP.dump"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
echo '=== Backup PostgreSQL before ANY write ==='
PGOPTIONS='-c default_transaction_read_only=on' pg_dump -h /var/run/postgresql -p 5433 -U benoit -d market_data_hub -Fc --file "$BACKUP"
[[ -s "$BACKUP" ]] || { echo 'FAIL empty backup'; exit 3; }
pg_restore --list "$BACKUP" > "$BACKUP_DIR/market_data_hub-before-research-staging-$STAMP.toc"
grep -q 'TABLE DATA.*eod_bars' "$BACKUP_DIR/market_data_hub-before-research-staging-$STAMP.toc" || { echo 'FAIL missing eod_bars in backup'; exit 3; }
sha256sum "$BACKUP" > "$BACKUP.sha256"
sha256sum -c "$BACKUP.sha256"
echo "BACKUP=$BACKUP"
echo '=== Snapshot legacy count before write ==='
BEFORE="$(PGOPTIONS='-c default_transaction_read_only=on' psql -XAt -h /var/run/postgresql -p 5433 -U benoit -d market_data_hub -c 'SELECT count(*) FROM public.eod_bars')"
curl -fsSL --max-time 30 "$ROOT/scripts/trading-factory-import-research-staging.py" -o "$TMP/import.py"
echo '=== Transactional import into mkd_research.yahoo_staging ==='
"$PY" "$TMP/import.py" --directory "$SOURCE" --backup "$BACKUP"
echo '=== Verify legacy data unchanged ==='
AFTER="$(PGOPTIONS='-c default_transaction_read_only=on' psql -XAt -h /var/run/postgresql -p 5433 -U benoit -d market_data_hub -c 'SELECT count(*) FROM public.eod_bars')"
[[ "$BEFORE" == "$AFTER" ]] || { echo "FAIL legacy bar count changed: $BEFORE -> $AFTER"; exit 4; }
echo "PASS legacy eod_bars count unchanged=$AFTER"
echo '=== Recovery ==='
echo "Verified backup: $BACKUP"
echo 'Restore must be performed separately into a NEW database after explicit approval; this script never restores over production.'
echo 'PIT=false PAPER=false; no scheduler starts or Git changes.'
