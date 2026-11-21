#!/usr/bin/env bash
# Continue Yahoo mapping evidence scan for remaining 800 instruments, no writes.
set -Eeuo pipefail
PY="$HOME/market-data-hub/.venv/bin/python"
[[ -x "$PY" ]] || { echo 'BLOCKED: MKD venv missing' >&2; exit 2; }
OUT="$HOME/trading-factory-reports/mkd-mapping-evidence/full-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT";chmod 700 "$OUT"
curl -fsSL --max-time 30 'https://raw.githubusercontent.com/besse79/market-data-hub/prep/recette-wsl-20261121/scripts/trading-factory-probe-yahoo-mappings.py?revision=09b1cf3dea2da68b4b10663bb77781a3cc9f76ea' -o "$OUT/probe.py"
# Fail immediately if a cached older probe without pagination was retrieved.
"$PY" "$OUT/probe.py" --help | grep -q -- '--offset' || {
 echo 'BLOCKED: stale probe version; --offset missing' >&2; exit 3;
}
for offset in $(seq 40 80 839);do
 echo "=== Mapping candidates $offset..$((offset+79)) / 840 ==="
 "$PY" "$OUT/probe.py" --output "$OUT/batch-$offset" --offset "$offset" --limit 80 --pause 1
done
"$PY" - "$OUT" <<'PY'
import csv,json,sys
from pathlib import Path
out=Path(sys.argv[1])
rows=[];summaries=[]
for d in sorted(out.glob('batch-*'),key=lambda p:int(p.name.split('-')[-1])):
 s=json.loads((d/'summary.json').read_text())
 summaries.append(s)
 with (d/'mapping-candidates.csv').open(newline='') as f:rows.extend(csv.DictReader(f))
ids=[r['instrument_id'] for r in rows]
if len(ids)!=800 or len(set(ids))!=800:raise RuntimeError('Incomplete or duplicate remaining 800')
with (out/'remaining-800-candidates.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
result={'probed':len(rows),'candidate_review':sum(r['status']=='CANDIDATE_REVIEW' for r in rows),
 'unresolved':sum(r['status']=='UNRESOLVED' for r in rows),
 'auto_mapped':0,'production_writes':False,'pit_verified':False,'paper_eligible':False}
(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
print('REPORT='+str(out/'summary.json'))
PY
