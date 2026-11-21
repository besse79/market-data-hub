#!/usr/bin/env bash
# Read-only metadata enrichment of the remaining 750 Yahoo candidates.
set -Eeuo pipefail
PY="$HOME/market-data-hub/.venv/bin/python"
INPUT="$HOME/trading-factory-reports/mkd-mapping-evidence/full-20261121T153607Z/remaining-800-candidates.csv"
[[ -x "$PY" && -f "$INPUT" ]] || { echo 'BLOCKED: Python venv or source CSV missing' >&2; exit 2; }
OUT="$HOME/trading-factory-reports/mkd-identity-evidence-full/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT";chmod 700 "$OUT"
SCRIPT="$OUT/identity.py"
curl -fsSL --retry 3 --max-time 60 'https://raw.githubusercontent.com/besse79/market-data-hub/13c5fe1af61e502bb5015b2e04a1219e4b60e039/scripts/trading-factory-yahoo-identity-evidence.py' -o "$SCRIPT"
"$PY" -m py_compile "$SCRIPT"
"$PY" - "$INPUT" <<'PY'
import csv,sys
with open(sys.argv[1],newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
ids=[r['instrument_id'] for r in rows]
if len(rows)!=800 or len(set(ids))!=800:raise SystemExit('BLOCKED: expected 800 unique source instruments')
print('PASS: source has 800 unique candidates')
PY
for offset in $(seq 50 50 799);do
 echo "=== Identity metadata $offset..$((offset+49)) / 800 ==="
 "$PY" "$SCRIPT" --input "$INPUT" --output "$OUT/batch-$offset" --offset "$offset" --limit 50 --pause 1.5
done
"$PY" - "$OUT" "$HOME/trading-factory-reports/mkd-identity-evidence-v2/identity-evidence.csv" <<'PY'
import csv,json,sys,collections
from pathlib import Path
out=Path(sys.argv[1]);first=Path(sys.argv[2])
if not first.is_file():raise SystemExit('BLOCKED: first 50 evidence file missing')
files=[first]+[out/f'batch-{i}'/'identity-evidence.csv' for i in range(50,800,50)]
rows=[]
for f in files:
 if not f.is_file():raise SystemExit('BLOCKED: missing batch '+str(f))
 with f.open(newline='',encoding='utf-8') as handle:batch=list(csv.DictReader(handle))
 if len(batch)!=50:raise SystemExit('BLOCKED: expected 50 rows in '+str(f))
 rows.extend(batch)
ids=[r['instrument_id'] for r in rows]
if len(rows)!=800 or len(set(ids))!=800:raise SystemExit('BLOCKED: incomplete or duplicate instrument coverage')
with (out/'identity-evidence-800.csv').open('w',newline='',encoding='utf-8') as handle:
 w=csv.DictWriter(handle,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
statuses=collections.Counter(r['status'] for r in rows)
reasons=collections.Counter(reason for r in rows for reason in r['reason'].split(';') if reason)
summary={'total':800,'unique_instruments':800,'statuses':dict(statuses),
 'provider_isin_available':sum(bool(r['provider_isin']) for r in rows),
 'provider_isin_missing':sum(not bool(r['provider_isin']) for r in rows),
 'reasons':dict(reasons),'certified':0,'database_writes':False,'pit_eligible':False,'paper_eligible':False}
(out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(summary,indent=2,ensure_ascii=False))
print('REPORT='+str(out/'summary.json'))
print('EVIDENCE='+str(out/'identity-evidence-800.csv'))
PY
