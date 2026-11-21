#!/usr/bin/env bash
set -euo pipefail
ROOT='https://raw.githubusercontent.com/besse79/market-data-hub/prep/recette-wsl-20261121'
PY="$HOME/market-data-hub/.venv/bin/python"
[[ -x "$PY" ]] || { echo 'FAIL: MKD virtualenv missing'; exit 2; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/src" "$TMP/tests"; touch "$TMP/src/__init__.py"
for f in src/daily_stage.py src/yahoo_capture.py src/bulk_stage.py tests/test_daily_stage.py tests/test_yahoo_capture.py tests/test_bulk_stage.py scripts/trading-factory-export-yahoo-manifest.py; do
 mkdir -p "$TMP/$(dirname "$f")"
 curl -fsSL --max-time 30 "$ROOT/$f" -o "$TMP/$f"
done
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BASE="$HOME/trading-factory-reports/mkd-integrated"
mkdir -p "$BASE"
LOG="$BASE/full-264-$STAMP.log"
exec > >(tee "$LOG") 2>&1
echo "=== Full 264 Yahoo capture $STAMP ==="
(cd "$TMP" && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TMP" "$PY" -m pytest -q -p no:cacheprovider tests)
MANIFEST="$BASE/manifests/$STAMP"
"$PY" "$TMP/scripts/trading-factory-export-yahoo-manifest.py" --output-dir "$MANIFEST"
OUT="$BASE/staging/2026-11-17_2026-11-21"
mkdir -p "$OUT"
echo "=== Resume all mapped symbols in $OUT ==="
(cd "$TMP" && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$TMP" timeout 1800 "$PY" - "$MANIFEST/yahoo-manifest.csv" "$OUT" <<'PY'
import json,sys
from src.bulk_stage import run
result=run(sys.argv[1],sys.argv[2],"2026-11-17","2026-11-21",max_symbols=264,delay=2)
print(json.dumps(result,indent=2,ensure_ascii=False))
if result["failed"]: sys.exit(3)
PY
)
echo "PASS full 264 manifest staged, no DB writes"
echo "LOG=$LOG"
echo "STAGING=$OUT"
