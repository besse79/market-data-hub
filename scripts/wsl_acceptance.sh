#!/usr/bin/env bash
# MKD V1 WSL acceptance: never connects to or modifies Weinstein'S.
set -Eeuo pipefail
umask 077
cd "$(dirname "$0")/.."
: "${DATABASE_URL:?Set DATABASE_URL for isolated MKD database}"
: "${W_MANIFEST:?Set W_MANIFEST to independently exported read-only W CSV}"
: "${MKD_RESTORE_TEST_URL:?Set MKD_RESTORE_TEST_URL for pre-created EMPTY _restore_test DB}"
[[ -f "$W_MANIFEST" ]] || { echo "W manifest not found: $W_MANIFEST" >&2; exit 2; }
# Validate parsed PostgreSQL URLs, not raw strings (credentials/ports/query may differ).
python - <<'PY'
import os
from sqlalchemy.engine import make_url
source = make_url(os.environ["DATABASE_URL"])
target = make_url(os.environ["MKD_RESTORE_TEST_URL"])
if source.get_backend_name() != "postgresql" or target.get_backend_name() != "postgresql":
    raise SystemExit("Only PostgreSQL databases are allowed")
if not source.database or not source.database.lower().startswith("mkd"):
    raise SystemExit("Refusing non-MKD source database; W must remain read-only")
if not target.database or not target.database.lower().startswith("mkd") or not target.database.endswith("_restore_test"):
    raise SystemExit("Restore target database must end in _restore_test")
if (source.host, source.port or 5432, source.database) == (target.host, target.port or 5432, target.database):
    raise SystemExit("Restore target must differ from MKD source")
print("MKD source database:", source.database, "restore target:", target.database)
PY
command -v pg_dump >/dev/null
command -v pg_restore >/dev/null
command -v psql >/dev/null
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="evidence/wsl-${STAMP}"
mkdir -p "$OUT"
exec > >(tee "$OUT/recipe.log") 2>&1
echo "MKD acceptance started UTC: $STAMP"
sha256sum "$W_MANIFEST" > "$OUT/w-manifest.sha256"
# Fail before any database write if the W manifest is incomplete or duplicated.
python -c 'import os; from pathlib import Path; from app.universe import parse_manifest; rows=parse_manifest(Path(os.environ["W_MANIFEST"])); print("W manifest instruments:", len(rows)); assert len(rows)==806, f"Expected 806 instruments, got {len(rows)}"'
python -m app.universe "$W_MANIFEST"
python -m app.backup "$OUT/mkd-before-import.dump"
python -m app.restore_verify "$OUT/mkd-before-import.dump"
python -m app.universe "$W_MANIFEST" --apply
python -m app.reconcile "$W_MANIFEST" --output "$OUT/reconcile.json"
python -m app.audit --manifest "$W_MANIFEST" --expected 806 --output "$OUT/coverage-before-collection.json"
echo "MKD import and backup/restore checks completed. Historical collection is a separate explicit operation."
echo "Evidence: $OUT"
