#!/usr/bin/env bash
# MKD V1 WSL acceptance: never connects to or modifies Weinstein'S.
set -Eeuo pipefail
umask 077
cd "$(dirname "$0")/.."
: "${DATABASE_URL:?Set DATABASE_URL for isolated MKD database}"
: "${W_MANIFEST:?Set W_MANIFEST to independently exported read-only W CSV}"
: "${MKD_RESTORE_TEST_URL:?Set MKD_RESTORE_TEST_URL for pre-created EMPTY _restore_test DB}"
[[ -f "$W_MANIFEST" ]] || { echo "W manifest not found: $W_MANIFEST" >&2; exit 2; }
[[ "${MKD_RESTORE_TEST_URL}" == *"_restore_test" ]] || { echo "Restore target must end _restore_test" >&2; exit 2; }
[[ "${DATABASE_URL}" != "${MKD_RESTORE_TEST_URL}" ]] || { echo "Restore target equals source" >&2; exit 2; }
command -v pg_dump >/dev/null
command -v pg_restore >/dev/null
command -v psql >/dev/null
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="evidence/wsl-${STAMP}"
mkdir -p "$OUT"
exec > >(tee "$OUT/recipe.log") 2>&1
echo "MKD acceptance started UTC: $STAMP"
sha256sum "$W_MANIFEST" > "$OUT/w-manifest.sha256"
python -m app.universe "$W_MANIFEST"
python -m app.backup "$OUT/mkd-before-import.dump"
python -m app.restore_verify "$OUT/mkd-before-import.dump"
python -m app.universe "$W_MANIFEST" --apply
python -m app.reconcile "$W_MANIFEST" --output "$OUT/reconcile.json"
python -m app.audit --manifest "$W_MANIFEST" --expected 806 --output "$OUT/coverage-before-collection.json"
echo "MKD import and backup/restore checks completed. Historical collection is a separate explicit operation."
echo "Evidence: $OUT"
